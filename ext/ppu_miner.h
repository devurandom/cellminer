#ifndef PPU_MINER_H
#define PPU_MINER_H

struct ppu_miner;

const int ppuminer_errstr_max;

int ppuminer_create(struct ppu_miner **miner, char *errstr);
void ppuminer_delete(struct ppu_miner *miner);
void ppuminer_setdebug(struct ppu_miner *miner);
void ppuminer_loadwork(struct ppu_miner *miner, const char *data, const char *target, unsigned long start_nonce, unsigned long range);
int ppuminer_run(struct ppu_miner *miner, unsigned long *nonce, char *errstr);
void ppuminer_stop(struct ppu_miner *miner);

#endif
