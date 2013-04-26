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

# include <stdint.h>
# include <stddef.h>
# include <stdlib.h>
# include <spu_mfcio.h>

# include "spu_slih.h"
# include "params.h"
# include "worker.h"
# include "util.h"

/*
 * NAME:	dma_get()
 * DESCRIPTION:	initiate DMA transfer from main memory to LS
 */
static
void dma_get(volatile void *ls, uint64_t ea, uint32_t size, uint32_t tag)
{
  mfc_get(ls, ea, size, tag, 0, 0);
}

/*
 * NAME:	dma_put()
 * DESCRIPTION:	initiate DMA transfer from LS to main memory
 */
static
void dma_put(volatile void *ls, uint64_t ea, uint32_t size, uint32_t tag)
{
  mfc_put(ls, ea, size, tag, 0, 0);
}

/*
 * NAME:	dma_params()
 * DESCRIPTION:	transfer work parameters between LS and main memory
 */
static
int dma_params(struct worker_params *params, uint64_t ea,
	       void (*dma)(volatile void *, uint64_t, uint32_t, uint32_t))
{
  uint32_t tag, size;

  tag = mfc_tag_reserve();
  if (tag == MFC_TAG_INVALID)
    return -1;

  /* size of data in struct, padded to a multiple of 128 */
  size = pad_to_128(offsetof(struct worker_params, padding));

  dma(params, ea, size, tag);

  mfc_write_tag_mask(1 << tag);
  mfc_read_tag_status_all();

  mfc_tag_release(tag);

  return 0;
}

/*
 * NAME:	signal_handler()
 * DESCRIPTION:	IRQ handler for signal notification
 */
static
unsigned int signal_handler(unsigned int events)
{
  if (spu_stat_signal1() &&
      spu_read_signal1())
    spu_stop(WORKER_IRQ_SIGNAL);

  return events & ~MFC_SIGNAL_NOTIFY_1_EVENT;
}

/*
 * NAME:	main()
 * DESCRIPTION:	entry point for SPU program
 */
int main(uint64_t speid, uint64_t argp, uint64_t envp)
{
  spu_id = speid;

  /* set up interrupt handler and enable interrupts */

  spu_slih_register(MFC_SIGNAL_NOTIFY_1_EVENT, signal_handler);

  spu_write_event_mask(MFC_SIGNAL_NOTIFY_1_EVENT);
  spu_ienable();

  /* loop forever loading parameters and doing work */

  while (1) {
    struct worker_params params __attribute__ ((aligned (128)));
    int result;

    /* load parameters */

    if (unlikely(dma_params(&params, argp, dma_get)))
      return WORKER_DMA_ERROR;

    debugging = params.flags & WORKER_FLAG_DEBUG;

    /* do work */

    if (unlikely(result = work_on(&params))) {
	/* we found something? */
	if (dma_params(&params, argp, dma_put))
	  return WORKER_DMA_ERROR;

	spu_stop(WORKER_FOUND_SOMETHING);
    }
    else
      spu_stop(WORKER_FOUND_NOTHING);
  }

  /* not reached */

  return 0;
}
