#!/usr/bin/python3

import os
dir = os.path.dirname(__file__)

import sys
sys.path.append(os.path.join(dir, "python"))
sys.path.append(os.path.join(dir, "python-bitcoinrpc"))
sys.path.append(os.path.join(dir, "python-blkmaker"))

import struct, threading, queue, time, argparse, socket, traceback, multiprocessing, logging
logging.basicConfig(format="%(asctime)s %(threadName)s: %(message)s")
log = logging.getLogger(__name__)

from miner import Miner
from cpu_miner import CPUMiner
from ppu_miner import PPUMiner
from spu_miner import SPUMiner

from getblocktemplate import GetBlockTemplate

import bitcoinrpc.authproxy
bitcoinrpc.authproxy.USER_AGENT = "Cell Miner/2.0"

def message(text):
	sys.stdout.write("{} >> {}\n".format(time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), text))

def message_indent(text):
	sys.stdout.write("                            {}\n".format(text))

optparser = argparse.ArgumentParser()
optparser.add_argument("pool_url")
optparser.add_argument("--ppe", type=int, default=multiprocessing.cpu_count())
optparser.add_argument("--spe", type=int, default=SPUMiner.usable_spes()-2)
optparser.add_argument("--debug", action="store_true")
options = optparser.parse_args()

if options.debug:
	logging.getLogger().setLevel(logging.DEBUG)

sharelog = {
	"start": int(time.time()),
	"accepted": 0,
	"rejected": 0,
	"failed": 0,
	"file": open("share." + socket.gethostname() + ".log", "w"),
}

miners = []

run = threading.Event()

work_queue = queue.Queue(maxsize=64)
send_queue = queue.Queue()

gbt = GetBlockTemplate(options.pool_url, run, work_queue, send_queue, sharelog=sharelog)

#sys.stdout.write("Creating 2 CPU miners\n")
#for i in range(2):
#	miners.append(Miner(CPUMiner(), run, send_queue, work_queue))
message("Creating {} PPE miners".format(options.ppe))
for i in range(options.ppe):
	miners.append(Miner(PPUMiner(), run, work_queue, send_queue))
message("Creating {} SPE miners".format(options.spe))
for i in range(options.spe):
	miner = SPUMiner()
	if options.debug:
		miner.setdebug()
	miners.append(Miner(miner, run, work_queue, send_queue))

run.set()

gbt.start()

for miner in miners:
	miner.start()

try:
	while True:
		if options.debug:
			threading.Event().wait(10)
		else:
			threading.Event().wait(30)

		rate = 0
		alive = 0
		for miner in miners:
			rate += miner.rate
			alive += (miner.alive > (time.time()-60)) and 1 or 0
		message("{:.3f} Mh/s | queues: T:{} W:{} | shares: A:{} R:{} F:{} since {}".format(rate/1000000, "?", work_queue.qsize(), sharelog["accepted"], sharelog["rejected"], sharelog["failed"], time.strftime("%Y-%m-%d %H-%M-%S", time.gmtime(sharelog["start"]))))
		log.debug("{} miners alive".format(alive))

		dead = len(miners) - alive
		if dead > 0:
			message_indent("WARNING: {} miners dead".format(dead))
except KeyboardInterrupt:
	message("Shutting down ...")
	run.clear()

	gbt.join()

	for miner in miners:
		miner.join()

	sharelog["file"].close()
