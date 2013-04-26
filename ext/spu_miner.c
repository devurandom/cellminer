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
#include <assert.h>

#include <libspe2.h>

#include "spu/params.h"

#include "spu_miner.h"

#define ERRSTR_MAX 128

struct spu_miner {
  /* must be first for proper alignment */
  volatile struct worker_params params;

  spe_context_ptr_t spe_context;
  uint32_t spe_entry;
  spe_stop_info_t stop_info;
};

static
void get_stop_reason(const spe_stop_info_t *stop_info,
		     const char **reason, int *code)
{
  switch (stop_info->stop_reason) {
  case SPE_EXIT:
    *reason = "SPE_EXIT";
    *code = stop_info->result.spe_exit_code;
    break;

  case SPE_STOP_AND_SIGNAL:
    *reason = "SPE_STOP_AND_SIGNAL";
    *code = stop_info->result.spe_signal_code;
    break;

  case SPE_RUNTIME_ERROR:
    *reason = "SPE_RUNTIME_ERROR";
    *code = stop_info->result.spe_runtime_error;
    break;

  case SPE_RUNTIME_EXCEPTION:
    *reason = "SPE_RUNTIME_EXCEPTION";
    *code = stop_info->result.spe_runtime_exception;
    break;

  case SPE_RUNTIME_FATAL:
    *reason = "SPE_RUNTIME_FATAL";
    *code = stop_info->result.spe_runtime_fatal;
    break;

  case SPE_CALLBACK_ERROR:
    *reason = "SPE_CALLBACK_ERROR";
    *code = stop_info->result.spe_callback_error;
    break;

  case SPE_ISOLATION_ERROR:
    *reason = "SPE_ISOLATION_ERROR";
    *code = stop_info->result.spe_isolation_error;
    break;

  default:
    *reason = "unknown reason";
    *code = -1;
  }
}

static void
report_error(struct spu_miner *miner, char errstr[ERRSTR_MAX]) {
	const char *reason;
	int code;

	get_stop_reason(&miner->stop_info, &reason, &code);

	if (miner->stop_info.stop_reason == SPE_EXIT && code == WORKER_DMA_ERROR) {
		strncpy(errstr, "SPE encountered DMA error", ERRSTR_MAX);
	}
	else {
		snprintf(errstr, ERRSTR_MAX, "SPE worker stopped with %s (0x%08x)", reason, code);
	}
}

const int spuminer_errstr_max = ERRSTR_MAX;

int
spuminer_create(struct spu_miner **miner, char errstr[ERRSTR_MAX]) {
	if (miner == NULL) {
		strncpy(errstr, "argument 'miner' may not be NULL", ERRSTR_MAX);
		return -1;
	}

	int err_align = posix_memalign((void**)miner, 128, sizeof(**miner));
	if (err_align) {
		strncpy(errstr, "unable to allocate aligned memory", ERRSTR_MAX);
		return -1;
	}

	(*miner)->spe_context = spe_context_create(0, NULL);
	if ((*miner)->spe_context == NULL) {
		free(*miner);

		strncpy(errstr, "failed to create SPE context", ERRSTR_MAX);
		return -1;
	}

	extern spe_program_handle_t spu_worker;
	if (spe_program_load((*miner)->spe_context, &spu_worker)) {
		spe_context_destroy((*miner)->spe_context);
		free(*miner);

		strncpy(errstr, "failed to load SPE program", ERRSTR_MAX);
		return -1;
	}

	(*miner)->spe_entry = SPE_DEFAULT_ENTRY;
	(*miner)->params.flags = 0;

	return 0;
}

void
spuminer_delete(struct spu_miner *miner) {
	if (miner == NULL) {
		return;
	}

	spe_context_destroy(miner->spe_context);
	free(miner);
}

void
spuminer_setdebug(struct spu_miner *miner) {
	miner->params.flags |= WORKER_FLAG_DEBUG;
}

void
spuminer_loadwork(struct spu_miner *miner, const char *data, const char *target, unsigned long start_nonce, unsigned long range) {
	memcpy((void*)miner->params.data.c,     data,    128);
	memcpy((void*)miner->params.target.c,   target,   32);

	miner->params.start_nonce = start_nonce;
	miner->params.range       = range;
}

int
spuminer_run(struct spu_miner *miner, unsigned long *nonce, char *errstr) {
	int err = spe_context_run(miner->spe_context, &miner->spe_entry, 0, (void*)&miner->params, 0, &miner->stop_info);
	if (err < 0) {
		snprintf(errstr, ERRSTR_MAX, "Error running SPE context: %s", strerror(errno));
		return -1;
	}

	if (miner->stop_info.stop_reason != SPE_STOP_AND_SIGNAL) {
		/* restart on next run */
		miner->spe_entry = SPE_DEFAULT_ENTRY;

		report_error(miner, errstr);
		return -1;
	}
	else {
		switch (miner->stop_info.result.spe_signal_code) {
		case WORKER_IRQ_SIGNAL:
			/* SPE is responding to our stop signal; restart on next run */
			miner->spe_entry = SPE_DEFAULT_ENTRY;
			/* fall through */
		case WORKER_FOUND_NOTHING:
			return 1;
		case WORKER_FOUND_SOMETHING:
			*nonce = miner->params.nonce;
			return 0;
		}
	}

	report_error(miner, errstr);
	return -1;
}

void
spuminer_stop(struct spu_miner *miner) {
	if (miner == NULL) {
		return;
	}

  /* signal SPE worker to stop */
  spe_signal_write(miner->spe_context, SPE_SIG_NOTIFY_REG_1, 1);
}

int
spuminer_physical_spes(void) {
	return spe_cpu_info_get(SPE_COUNT_PHYSICAL_SPES, -1);
}

int
spuminer_usable_spes(void) {
	return spe_cpu_info_get(SPE_COUNT_USABLE_SPES, -1);
}
