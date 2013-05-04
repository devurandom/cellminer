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

# include <stdlib.h>
# include <stdint.h>
# include <string.h>

# include <ruby.h>

# include "ppu_miner.h"

struct rb_ppu_miner {
  struct ppu_miner *miner;
  unsigned long nonce;
  char errstr[128];
};

static
VALUE m_initialize(int argc, VALUE *argv, VALUE self)
{
  struct rb_ppu_miner *miner;

  if (argc < 0 || argc > 1)
    rb_raise(rb_eArgError, "wrong number of arguments (%d for 0..1)", argc);

  Data_Get_Struct(self, struct rb_ppu_miner, miner);

  if (argc > 0 && RTEST(argv[0]))
    ppuminer_setdebug(miner->miner);

  return self;
}

static
VALUE run_miner(void *data)
{
  struct rb_ppu_miner *miner = data;

  int err = ppuminer_run(miner->miner, &miner->nonce, miner->errstr);
  if (err < 0)
    return Qnil;
  else if (err > 0)
    return Qfalse;

  return Qtrue;
}

static
void unblock_miner(void *data)
{
  struct rb_ppu_miner *miner = data;

  ppuminer_stop(miner->miner);
}

static
VALUE m_run(VALUE self, VALUE data, VALUE target, VALUE midstate,
	    VALUE start_nonce, VALUE range)
{
  struct rb_ppu_miner *miner;
  VALUE retval;

  Data_Get_Struct(self, struct rb_ppu_miner, miner);

  /* prepare parameters */

  StringValue(data);
  StringValue(target);

  if (RSTRING_LEN(data) != 128)
    rb_raise(rb_eArgError, "data must be 128 bytes");
  if (RSTRING_LEN(target) != 32)
    rb_raise(rb_eArgError, "target must be 32 bytes");

  ppuminer_loadwork(miner->miner, RSTRING_PTR(data), RSTRING_PTR(target), NUM2ULONG(start_nonce), NUM2ULONG(range));

  miner->nonce = 0;
  memset(miner->errstr, '\0', sizeof(miner->errstr));

  /* unlock the Global Interpreter Lock and run the SPE context */

  retval = rb_thread_blocking_region(run_miner, miner,
				     unblock_miner, miner);

  switch (retval) {
  case Qtrue: {
    union {
      char c[128];
      uint32_t u[32];
    } _data;
    memcpy(_data.c, RSTRING_PTR(data), 128);
    _data.u[19] = miner->nonce;
    retval = rb_str_new(_data.c, 128);
    } break;

  case Qnil:
    rb_raise(rb_eRuntimeError, "%s", miner->errstr);
  }

  return retval;
}

static
void i_free(struct rb_ppu_miner *miner)
{
  ppuminer_delete(miner->miner);
  free(miner);
}

static
VALUE i_allocate(VALUE klass)
{
  struct rb_ppu_miner *miner = malloc(sizeof(*miner));

  int err = ppuminer_create(&miner->miner, miner->errstr);
  if (err < 0) {
    rb_raise(rb_eRuntimeError, "%s", miner->errstr);
  }

  return Data_Wrap_Struct(klass, 0, i_free, miner);
}

void Init_ppu_miner(VALUE container)
{
  VALUE cPPUMiner;

  cPPUMiner = rb_define_class_under(container, "PPUMiner", rb_cObject);
  rb_define_alloc_func(cPPUMiner, i_allocate);

  rb_define_method(cPPUMiner, "initialize", m_initialize, -1);
  rb_define_method(cPPUMiner, "run", m_run, 5);
}
