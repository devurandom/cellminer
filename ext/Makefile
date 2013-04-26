EMBEDSPU=$(CROSS_COMPILE)embedspu
CC=$(CROSS_COMPILE)gcc

WARN=-Wall -Werror
DEBUG=-g

PYTHON_CPPFLAGS=$(shell pkg-config --cflags-only-I python-3.2)
PYTHON_CFLAGS=$(shell pkg-config --cflags-only-other python-3.2)

CFLAGS=$(PYTHON_CFLAGS) $(WARN) $(DEBUG) -std=c11 -D_XOPEN_SOURCE=700
CPPFLAGS=$(PYTHON_CPPFLAGS)

all: libcellminer.so

spu_miner.o: spu_miner.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ -c $<

libcellminer.so: \
		spu_miner.o \
		ppu_miner.o \
		spu_worker.o \
		ppu/worker.a
	$(CC) -shared -o $@ $^ -lspe2 -lpython3.2

spu_worker.o: spu/worker.elf
	$(EMBEDSPU) spu_worker $< $@

spu/worker.elf: spu/Makefile spu/*.[chs]
	$(MAKE) -C spu

ppu/worker.a: ppu/Makefile ppu/*.[chs]
	$(MAKE) -C ppu

clean: spu/clean ppu/clean
	$(RM) *.o *.so

.PHONY: spu/clean
spu/clean:
	$(MAKE) -C spu clean

.PHONY: ppu/clean
ppu/clean:
	$(MAKE) -C ppu clean

depend.auto: *.[ch]
	@$(CC) -MM *.c >$@

*.o: Makefile

include depend.auto
