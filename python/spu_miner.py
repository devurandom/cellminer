import os
dir = os.path.dirname(__file__)

from ctypes import *

cellminer = cdll.LoadLibrary(os.path.join(dir, "../ext/libcellminer.so"))

spuminer_errstr_max = c_int.in_dll(cellminer, "spuminer_errstr_max").value

spuminer_create = cellminer.spuminer_create
spuminer_create.argtypes = [POINTER(c_void_p), c_char_p]
spuminer_create.restype = c_int

spuminer_delete = cellminer.spuminer_delete
spuminer_delete.argtypes = [c_void_p]
spuminer_delete.restype = None

spuminer_setdebug = cellminer.spuminer_setdebug
spuminer_setdebug.argtypes = [c_void_p]
spuminer_setdebug.restype = None

spuminer_loadwork = cellminer.spuminer_loadwork
spuminer_loadwork.argtypes = [c_void_p, c_char_p, c_char_p, c_ulong, c_ulong]
spuminer_loadwork.restype = None

spuminer_run = cellminer.spuminer_run
spuminer_run.argtypes = [c_void_p, POINTER(c_ulong), c_char_p]
spuminer_run.restype = c_int

spuminer_stop = cellminer.spuminer_stop
spuminer_stop.argtypes = [c_void_p]
spuminer_stop.restype = None

spuminer_physical_spes = cellminer.spuminer_physical_spes
spuminer_physical_spes.argtypes = []
spuminer_physical_spes.restype = c_int

spuminer_usable_spes = cellminer.spuminer_usable_spes
spuminer_usable_spes.argtypes = []
spuminer_usable_spes.restype = c_int

class SPUMiner:
	def __init__(self):
		self.miner = c_void_p()
		errstr = create_string_buffer(b'\0' * spuminer_errstr_max)
		err = spuminer_create(byref(self.miner), errstr)
		if err < 0:
			raise RuntimeError(errstr.raw.decode('ascii'))

	def __del__(self):
		self.stop()
		spuminer_delete(self.miner)

	def setdebug(self):
		return spuminer_setdebug(self.miner)

	def loadwork(self, data, target, start_nonce, range):
		assert(len(data) == 128)
		assert(len(target) == 32)

		spuminer_loadwork(self.miner, data, target, start_nonce, range)

	def run(self):
		nonce = c_ulong(0)
		errstr = create_string_buffer(b'\0' * spuminer_errstr_max)
		err = spuminer_run(self.miner, byref(nonce), errstr)
		if err < 0:
			raise RuntimeError(errstr.raw.decode('ascii'))
		elif err > 0:
			return None

		return nonce.value
		
	def stop(self):
		spuminer_stop(self.miner)

	@staticmethod
	def physical_spes():
		return spuminer_physical_spes()

	@staticmethod
	def usable_spes():
		return spuminer_usable_spes()
