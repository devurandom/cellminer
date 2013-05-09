import os
dir = os.path.dirname(__file__)

from ctypes import *

cellminer = cdll.LoadLibrary(os.path.join(dir, "../ext/libcellminer.so"))

ppuminer_errstr_max = c_int.in_dll(cellminer, "ppuminer_errstr_max").value

ppuminer_create = cellminer.ppuminer_create
ppuminer_create.argtypes = [POINTER(c_void_p), c_char_p]
ppuminer_create.restype = c_int

ppuminer_delete = cellminer.ppuminer_delete
ppuminer_delete.argtypes = [c_void_p]
ppuminer_delete.restype = None

ppuminer_setdebug = cellminer.ppuminer_setdebug
ppuminer_setdebug.argtypes = [c_void_p]
ppuminer_setdebug.restype = None

ppuminer_loadwork = cellminer.ppuminer_loadwork
ppuminer_loadwork.argtypes = [c_void_p, c_char_p, c_char_p, c_ulong, c_ulong]
ppuminer_loadwork.restype = None

ppuminer_run = cellminer.ppuminer_run
ppuminer_run.argtypes = [c_void_p, POINTER(c_ulong), c_char_p]
ppuminer_run.restype = c_int

ppuminer_stop = cellminer.ppuminer_stop
ppuminer_stop.argtypes = [c_void_p]
ppuminer_stop.restype = None

class PPUMiner:
	def __init__(self):
		self.miner = c_void_p()
		errstr = create_string_buffer(b'\0' * ppuminer_errstr_max)
		err = ppuminer_create(byref(self.miner), errstr)
		if err < 0:
			raise RuntimeError(errstr.raw.decode('ascii'))

	def __del__(self):
		self.stop()
		ppuminer_delete(self.miner)

	def setdebug(self):
		return ppuminer_setdebug(self.miner)

	def loadwork(self, data, target, start_nonce, range):
		assert(len(data) == 128)
		assert(len(target) == 32)

		ppuminer_loadwork(self.miner, data, target, start_nonce, range)

	def run(self):
		nonce = c_ulong(0)
		errstr = create_string_buffer(b'\0' * ppuminer_errstr_max)
		err = ppuminer_run(self.miner, byref(nonce), errstr)
		if err < 0:
			raise RuntimeError(errstr.raw.decode('ascii'))
		elif err > 0:
			return None

		return nonce.value

	def stop(self):
		ppuminer_stop(self.miner)
