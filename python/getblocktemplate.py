import binascii, struct, traceback, threading, queue, logging, time, sys
log = logging.getLogger(__name__)

import blktemplate
import jsonrpc

NSLICES = 128
QUANTUM = int(0x100000000 / NSLICES)

RETRIES = 10

def message(text):
	sys.stdout.write("{} >> {}\n".format(time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), text))

def message_indent(text):
	sys.stdout.write("                            {}\n".format(text))

def print_json(req):
	sys.stdout.write(json.dumps(req, indent=4))

class GetTemplate(threading.Thread):
	def __init__(self, pool_url, run, tmpl_queue):
		super(GetTemplate, self).__init__()
		self.name = "gettmpl"
		self._pool_url = pool_url
		self._run = run
		self._tmpl_queue = tmpl_queue
		self.reconnect()

	def reconnect(self):
		self._service = jsonrpc.ServiceProxy(self._pool_url, "getblocktemplate")

	def request(self, req):
		for i in range(RETRIES):
			try:
				return self._service(*req["params"])
			except:
				traceback.print_exc()
				self.reconnect()

	def run(self):
		while self._run.is_set():
			tmpl = blktemplate.Template()
			req = tmpl.request()

			log.debug("Requesting template")
			resp = self.request(req)
			if not resp:
				message_indent("Template request failed")
				continue
	
			tmpl.add(resp)

			tmpl.target = binascii.a2b_hex(resp["target"].encode("ascii"))

			log.debug("Received template")
			try:
				self._tmpl_queue.put(tmpl, timeout=tmpl.time_left()/4)
			except queue.Full:
				pass
		log.debug("exiting")

class Longpoll(threading.Thread):
	def __init__(self, pool_url, run, lp_queue):
		super(Longpoll, self).__init__()
		self.name = "Longpoll"
		self._pool_url = pool_url
		self._run = run
		self._lp_queue = lp_queue
		self._lpid = None
		self.reconnect()

	def reconnect(self):
		self._service = jsonrpc.ServiceProxy(self._pool_url, "getblocktemplate", timeout=60*60)

	def longpoll(self, req):
		for i in range(RETRIES):
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

			with self._lp_queue.mutex:
				self._lp_queue.queue.clear()

			log.debug("Received template from longpoll")
			self._lp_queue.put(tmpl)
		log.debug("exiting")

class SendWork(threading.Thread):
	def __init__(self, pool_url, run, send_queue, sharelog = None):
		super(SendWork, self).__init__()
		self.name = "sendwork"
		self._pool_url = pool_url
		self._run = run
		self._send_queue = send_queue
		self._sharelog = sharelog
		self.reconnect()

	def reconnect(self):
		self._service = jsonrpc.ServiceProxy(self._pool_url, "submitblock")

	def request(self, req):
		for i in range(RETRIES):
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
				self._sharelog["file"].write("{} {} {}".format(int(time.time()), binascii.b2a_hex(data).decode("ascii"), nonce))
				if resp:
					message("Sending nonce: Accepted")
					if self._sharelog:
						self._sharelog["accepted"] += 1
						self._sharelog["file"].write(" accepted\n")
				elif not resp and not err:
					message("Sending nonce: Failed")
					if self._sharelog:
						self._sharelog["failed"] += 1
						self._sharelog["file"].write(" failed\n")
				else:
					message("Sending nonce: Rejected")
					message_indent("Reason: {}".format(err))
					if self._sharelog:
						self._sharelog["rejected"] += 1
						self._sharelog["file"].write(" rejected\n")
				if self._sharelog:
					self._sharelog["file"].flush()
			except:
				traceback.print_exc()
		log.debug("exiting")

class MakeWork(threading.Thread):
	def __init__(self, run, work_queue, tmpl_queue, lp_queue):
		super(MakeWork, self).__init__()
		self.name = "makework"
		self._run = run
		self._work_queue = work_queue
		self._tmpl_queue = tmpl_queue
		self._lp_queue = lp_queue

	def next(self, tmpl):
		return not self._run.is_set() or not self._lp_queue.empty() or not tmpl.time_left() or not tmpl.work_left()

	def run(self):
		while self._run.is_set():
			log.debug("waiting ({})".format(self._tmpl_queue.qsize()))
			tmpl = None
			q = None
			try:
				tmpl = self._lp_queue.get(block=False)
				q = self._lp_queue
				message("Got template from longpoll")
			except queue.Empty:
				tmpl = self._tmpl_queue.get()
				q = self._tmpl_queue
				message("Got template")

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

			log.debug("clearing because: {} {} {} {}".format(self._run.is_set(), self._lp_queue.empty(), tmpl.time_left(), tmpl.work_left()))
			with self._work_queue.mutex:
				self._work_queue.queue.clear()

			log.debug("Finished template ({} queued)".format(self._tmpl_queue.qsize()))
			q.task_done()
		log.debug("exiting")

class GetBlockTemplate:
	def __init__(self, pool_url, run, work_queue, send_queue, sharelog = None):
		lp_queue = queue.Queue(maxsize=1)
		tmpl_queue = queue.Queue(maxsize=1)

		self._gettmpl = GetTemplate(pool_url, run, tmpl_queue)
		self._longpoll = Longpoll(pool_url, run, lp_queue)
		self._sendwork = SendWork(pool_url, run, send_queue, sharelog)
		self._makework = MakeWork(run, work_queue, tmpl_queue, lp_queue)

	def start(self):
		self._gettmpl.start()
		self._longpoll.start()
		self._sendwork.start()
		self._makework.start()

	def join(self):
		self._gettmpl.join()
		self._longpoll.join()
		self._sendwork.join()
		self._makework.join()
