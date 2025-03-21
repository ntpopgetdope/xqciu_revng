#!/bin/sh

[ ! -d build ] && exit

cp build/*.decode submodules/xqci/target/riscv/xqci/
cp build/xqciu_tcg.c submodules/xqci/target/riscv/xqci/
cp build/xqciu_tcg.h submodules/xqci/target/riscv/xqci/
cp build/xqciu_trans.c.inc submodules/xqci/target/riscv/xqci/
cp build/xqciu_csr.c submodules/xqci/target/riscv/xqci/
cp build/xqciu_csr.h submodules/xqci/target/riscv/xqci/
cp xqciu_tcg_manual.c.inc submodules/xqci/target/riscv/xqci/
cp xqci_helper.h submodules/xqci/target/riscv/xqci/

# Disas
cp build/riscv-xqci.c submodules/xqci/disas/
cp build/riscv-xqci.h submodules/xqci/disas/
cp build/riscv-xqci-16-decode.c.inc submodules/xqci/disas/
cp build/riscv-xqci-32-decode.c.inc submodules/xqci/disas/
cp build/riscv-xqci-48-decode.c.inc submodules/xqci/disas/
cp build/riscv-xqci-trans.c.inc submodules/xqci/disas/

# Testing
rm -r submodules/xqci/tests/tcg/riscv32/klee_io
rm -r submodules/xqci/tests/tcg/riscv32/Xqci
cp -r build/klee/io submodules/xqci/tests/tcg/riscv32/klee_io
cp -r submodules/riscv-unified-db/arch_overlay/qc_iu/inst/Xqci/ submodules/xqci/tests/tcg/riscv32/
cp scripts/assemble.py submodules/xqci/tests/tcg/riscv32/
cp scripts/c.py submodules/xqci/tests/tcg/riscv32/
cp scripts/common.py submodules/xqci/tests/tcg/riscv32/
