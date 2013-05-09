import time, socket, logging, threading
log = logging.getLogger(__name__)

class Miner(threading.Thread):
	def __init__(self, miner, run, work_queue, send_queue):
		super(Miner, self).__init__()
		self.daemon = True
		self.name = "{} ({})".format(self.name, repr(type(miner)))
		self.miner = miner
		self.rate = 0
		self.alive = 0
		self._run = run
		self._work_queue = work_queue
		self._send_queue = send_queue

	def run(self):
		while self._run.is_set():
			start = time.time()
			self.alive = start

			log.debug("waiting ({})".format(self._work_queue.qsize()))
			work = self._work_queue.get()
			tmpl, dataid, data, target, start_nonce, r = work

			log.debug("working")
			self.miner.loadwork(data, target, start_nonce, r)

			nonce = self.miner.run()
			if nonce:
				log.debug("found {} for {} -> {}".format(nonce, dataid, data))
				nonce = socket.ntohl(nonce)
				self._send_queue.put([tmpl, dataid, data[:76], nonce])

			self._work_queue.task_done()

			if not nonce:
				stop = time.time()
				self.rate = r / (stop - start)
