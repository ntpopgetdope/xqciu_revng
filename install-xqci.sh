#!/bin/sh

[ ! -d build ] && exit

cp build/*.decode submodules/xqci/target/riscv/xqci/
cp build/xqciu_tcg.c submodules/xqci/target/riscv/xqci/
cp build/xqciu_tcg.h submodules/xqci/target/riscv/xqci/
cp build/xqciu_trans.c.inc submodules/xqci/target/riscv/xqci/
cp build/riscv-xqci.c submodules/xqci/disas/
cp build/riscv-xqci.h submodules/xqci/disas/
cp build/riscv-xqci-16-decode.c.inc submodules/xqci/disas/
cp build/riscv-xqci-32-decode.c.inc submodules/xqci/disas/
cp build/riscv-xqci-48-decode.c.inc submodules/xqci/disas/
