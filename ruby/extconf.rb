#
# cellminer - Bitcoin miner for the Cell Broadband Engine Architecture
# Copyright © 2011 Robert Leslie
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License (version 2) as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

require 'mkmf'

$objs = ['rb_cellminer.o',
         'rb_spu_miner.o',
         'rb_ppu_miner.o',
         'libcellminer.so']

$CFLAGS << ' -Wall -I../ext'
$LDFLAGS << ' -Wl,-rpath="\$$ORIGIN/../ext"'

raise "missing libspe2" unless have_library('spe2', 'spe_context_run')

create_makefile 'rbcellminer'
