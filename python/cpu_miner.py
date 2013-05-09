import struct

from blkmaker import _dblsha256

class CPUMiner:
	def loadwork(self, data, target, start_nonce, r):
		self.data = data
		self.target = target
		self.start_nonce = start_nonce
		self.range = r

	def run(self):
		for nonce in range(self.start_nonce, self.start_nonce + self.range - 1):
			_data = self.data[:76] + struct.pack('!I', nonce)
			blkhash = _dblsha256(_data)
			if blkhash[28:] == b'\0\0\0\0':
				sys.stdout.write("Found nonce: 0x%8x \n" % nonce)
				return nonce
			if (not (nonce % 0x1000)):
				sys.stdout.write("0x%8x hashes done...\r" % nonce)
				sys.stdout.flush()
