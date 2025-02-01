#!/bin/sh

[ ! -d build ] && exit

cp build/*.decode submodules/xqci/target/riscv/xqci/
cp build/xqciu_tcg.c submodules/xqci/target/riscv/xqci/
cp build/xqciu_tcg.h submodules/xqci/target/riscv/xqci/
cp build/xqciu_trans.c.inc submodules/xqci/target/riscv/xqci/
cp build/xqciu-decode-extra-16.c.inc submodules/xqci/target/riscv/xqci/
cp build/xqciu-decode-extra-32.c.inc submodules/xqci/target/riscv/xqci/
cp build/xqciu-decode-extra-48.c.inc submodules/xqci/target/riscv/xqci/
