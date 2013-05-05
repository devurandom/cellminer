import sys
sys.path.append("python-blkmaker")
sys.path.append("python-bitcoinrpc")

import binascii, struct, traceback, threading, queue, logging, time
log = logging.getLogger(__name__)

import blktemplate
import jsonrpc

NSLICES = 128
QUANTUM = int(0x100000000 / NSLICES)

def message(text):
	sys.stdout.write("{} >> {}\n".format(time.strftime("%c"), text))

def message_indent(text):
	sys.stdout.write("                            {}\n".format(text))

def print_json(req):
	sys.stdout.write(json.dumps(req, indent=4))

class GetTemplate(threading.Thread):
	def __init__(self, pool_url, run, tmpl_queue, needtmpl):
		super(GetTemplate, self).__init__()
		self.name = "gettmpl"
		self._pool_url = pool_url
		self._run = run
		self._tmpl_queue = tmpl_queue
		self._needtmpl = needtmpl
		self.reconnect()

	def reconnect(self):
		self._service = jsonrpc.ServiceProxy(self._pool_url, "getblocktemplate")

	def request(self, req):
		try:
			return self._service(*req["params"])
		except:
			traceback.print_exc()
			self.reconnect()

	def run(self):
		while self._run.is_set():
			self._needtmpl.wait()

			tmpl = blktemplate.Template()
			req = tmpl.request()

			log.debug("Requesting template")
			resp = self.request(req)
			if not resp:
				message_indent("Template request failed")
				continue
	
			tmpl.add(resp)

			tmpl.target = binascii.a2b_hex(resp["target"].encode("ascii"))

			message("Received template")
			self._tmpl_queue.put(tmpl)

			self._needtmpl.clear()
		log.debug("exiting")

class Longpoll(threading.Thread):
	def __init__(self, pool_url, run, tmpl_queue, nexttmpl):
		super(Longpoll, self).__init__()
		self.name = "Longpoll"
		self._pool_url = pool_url
		self._run = run
		self._tmpl_queue = tmpl_queue
		self._nexttmpl = nexttmpl
		self._lpid = None
		self.reconnect()

	def reconnect(self):
		self._service = jsonrpc.ServiceProxy(self._pool_url, "getblocktemplate", timeout=60*60)

	def longpoll(self, req):
		try:
			return self._service(*req["params"])
		except:
			traceback.print_exc()
			self.reconnect()

	def run(self):
		while self._run.is_set():
			tmpl = blktemplate.Template()
			req = tmpl.request(lpid=self._lpid)

			log.debug("Initiating longpoll")
			resp = self.longpoll(req)
			if not resp:
				message_indent("Longpoll failed")
				continue

			tmpl.add(resp)

			self._lpid = resp["longpollid"]
			tmpl.target = binascii.a2b_hex(resp["target"].encode("ascii"))

			with self._tmpl_queue.mutex:
				self._tmpl_queue.queue.clear()

			self._nexttmpl.set()

			message("Received template from longpoll")
			self._tmpl_queue.put(tmpl)
		log.debug("exiting")

class MakeWork(threading.Thread):
	def __init__(self, run, work_queue, tmpl_queue, nexttmpl, needtmpl):
		super(MakeWork, self).__init__()
		self.name = "makework"
		self._run = run
		self._work_queue = work_queue
		self._tmpl_queue = tmpl_queue
		self._nexttmpl = nexttmpl
		self._needtmpl = needtmpl

	def next(self, tmpl):
		return not self._run.is_set() or self._nexttmpl.is_set() or not tmpl.time_left() or not tmpl.work_left()

	def run(self):
		while self._run.is_set():
			log.debug("waiting ({})".format(self._tmpl_queue.qsize()))
			tmpl = self._tmpl_queue.get()

			self._nexttmpl.clear()

			message("Working on next template")
			while (not self.next(tmpl)):
				log.debug("time left: {}".format(tmpl.time_left()))

				(data, dataid) = tmpl.get_data()

				log.debug("{} -> {}".format(dataid, data))
				assert(len(data) == 76)

				buf = bytearray(128)
				struct.pack_into("76s", buf, 0, data)
				struct.pack_into(">B", buf, 80, 128)
				struct.pack_into(">Q", buf, 120, 80*8)
				data = bytes(buf)

				r = QUANTUM
				for i in range(NSLICES):
					start_nonce = i * QUANTUM
					self._work_queue.put([tmpl, dataid, data, tmpl.target, start_nonce, r])
					if self.next(tmpl):
						break
					if tmpl.time_left() < 10 and self._tmpl_queue.empty():
						log.debug("Requesting next template")
						self._needtmpl.set()

			log.debug("ended because: {} {} {} {}".format(self._run.is_set(), not self._nexttmpl.is_set(), tmpl.time_left(), tmpl.work_left()))

			if self._tmpl_queue.empty():
				self._needtmpl.set()

			log.debug("clearing")
			with self._work_queue.mutex:
				self._work_queue.queue.clear()

			message("Finished template ({} queued)".format(self._tmpl_queue.qsize()))
			self._tmpl_queue.task_done()
		log.debug("exiting")

class SendWork(threading.Thread):
	def __init__(self, pool_url, run, send_queue):
		super(SendWork, self).__init__()
		self.name = "sendwork"
		self._pool_url = pool_url
		self._run = run
		self._send_queue = send_queue
		self.reconnect()

	def reconnect(self):
		self._service = jsonrpc.ServiceProxy(self._pool_url, "submitblock")

	def request(self, req):
		try:
			resp = self._service(*req["params"])

			if not resp:
				return (True, None)
			else:
				return (None, resp)
		except:
			traceback.print_exc()
			self.reconnect()
			return (None, None)

	def run(self):
		while self._run.is_set():
			send = self._send_queue.get()
			tmpl, dataid, data, nonce = send

			req = tmpl.submit(data, dataid, nonce)
			try:
				resp, err = self.request(req)
				if resp:
					message("Sending nonce: Accepted")
				else:
					message("Sending nonce: Rejected")
					message_indent("Reason: {}".format(err))
			except:
				traceback.print_exc()
		log.debug("exiting")

class GetBlockTemplate:
	def __init__(self, pool_url, run, work_queue, send_queue):
		tmpl_queue = queue.Queue(maxsize=128)

		needtmpl = threading.Event()
		nexttmpl = threading.Event()

		self._makework = MakeWork(run, work_queue, tmpl_queue, nexttmpl, needtmpl)
		self._sendwork = SendWork(pool_url, run, send_queue)
		self._gettmpl = GetTemplate(pool_url, run, tmpl_queue, needtmpl)
		self._longpoll = Longpoll(pool_url, run, tmpl_queue, nexttmpl)

	def start(self):
		self._makework.start()
		self._sendwork.start()
		self._gettmpl.start()
		self._longpoll.start()

	def stop(self):
		self._makework.join()
		self._sendwork.join()
		self._gettmpl.join()
		self._longpoll.join()
