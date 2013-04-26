#ifndef SPU_MINER_H
#define SPU_MINER_H

struct spu_miner;

const int spuminer_errstr_max;

int spuminer_create(struct spu_miner **miner, char *errstr);
void spuminer_delete(struct spu_miner *miner);
void spuminer_setdebug(struct spu_miner *miner);
void spuminer_loadwork(struct spu_miner *miner, const char *data, const char *target, unsigned long start_nonce, unsigned long range);
int spuminer_run(struct spu_miner *miner, unsigned long *nonce, char *errstr);
void spuminer_stop(struct spu_miner *miner);
int spuminer_physical_spes(void);
int spuminer_usable_spes(void);

#endif
