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

RUBY	= ruby1.9.1

all: ext/libcellminer.so ruby/rbcellminer.so

ext/libcellminer.so: ext/Makefile ext/*.[ch]  \
		ext/spu/Makefile ext/spu/*.[chs]  \
		ext/ppu/Makefile ext/ppu/*.[chs]
	$(MAKE) -C ext

ruby/rbcellminer.so: ruby/Makefile ruby/*.[ch]  \
		ext/libcellminer.so
	cp -a  ext/libcellminer.so ruby/
	$(MAKE) -C ruby

ruby/Makefile: ruby/extconf.rb ruby/depend
	$(RUBY) -C ruby -E ascii-8bit extconf.rb

.PHONY: clean
clean:
	$(MAKE) -C ext $@
	$(MAKE) -C ruby $@

.PHONY: again
again: clean
	$(MAKE)
