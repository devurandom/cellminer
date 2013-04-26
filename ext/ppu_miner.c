/*
 * cellminer - Bitcoin miner for the Cell Broadband Engine Architecture
 * Copyright © 2011 Robert Leslie
 *
 * This program is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License (version 2) as
 * published by the Free Software Foundation.
 *
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program; if not, write to the Free Software Foundation, Inc.,
 * 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 */

#include <stdlib.h>
#include <stdint.h>
#include <string.h>

#include "ppu/params.h"

#include "ppu_miner.h"

#define ERRSTR_MAX 128

extern int ppu_mine(volatile struct worker_params *);

struct ppu_miner {
  volatile struct worker_params params;
};

const int ppuminer_errstr_max = ERRSTR_MAX;

int
ppuminer_create(struct ppu_miner **miner, char errstr[ERRSTR_MAX]) {
	if (miner == NULL) {
		strncpy(errstr, "argument 'miner' may not be NULL", ERRSTR_MAX);
		return -1;
	}

	int err_align = posix_memalign((void**)miner, 128, sizeof(**miner));
	if (err_align) {
		strncpy(errstr, "unable to allocate aligned memory", ERRSTR_MAX);
		return -1;
	}

	(*miner)->params.flags = 0;

	return 0;
}

void
ppuminer_delete(struct ppu_miner *miner) {
	if (miner == NULL) {
		return;
	}

	free(miner);
}

void
ppuminer_setdebug(struct ppu_miner *miner) {
    miner->params.flags |= WORKER_FLAG_DEBUG;
}

void
ppuminer_loadwork(struct ppu_miner *miner, const char *data, const char *target, unsigned long start_nonce, unsigned long range) {
	memcpy((void*)miner->params.data.c,     data,    128);
	memcpy((void*)miner->params.target.c,   target,   32);

	miner->params.start_nonce = start_nonce;
	miner->params.range       = range;
}

int
ppuminer_run(struct ppu_miner *miner, unsigned long *nonce, char *errstr) {
	int ret = ppu_mine(&miner->params);
	switch (ret) {
	case WORKER_FOUND_SOMETHING:
		*nonce = miner->params.nonce;
		return 0;
	case WORKER_FOUND_NOTHING:
		return 1;
	}

	strncpy(errstr, "unknown error", ERRSTR_MAX);
	return -1;
}

void
ppuminer_stop(struct ppu_miner *miner) {
	if (miner == NULL) {
		return;
	}
}
