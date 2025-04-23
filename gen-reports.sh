#!/bin/sh

./scripts/report.py \
    --prioritized=risc-v-qualcomm-instruction-priority-v2.csv \
    --inst-dir=submodules/riscv-unified-db/arch_overlay/qc_iu/inst/Xqci \
    --enabled=build/xqciu_tcg.h \
    --io=build/xqci/klee/io \
    --out=reports/xqci-$(date +'%Y-%m-%d')


./scripts/report.py \
    --inst-dir=submodules/riscv-unified-db/arch_overlay/qc_iu/inst/Xqccmp \
    --enabled=build/xqccmp_tcg.h \
    --io=build/xqccmp/klee/io \
    --out=reports/xqccmp-$(date +'%Y-%m-%d')


./scripts/report.py \
    --inst-dir=submodules/riscv-unified-db/arch/inst/Smrnmi \
    --enabled=build/smrnmi_tcg.h \
    --io=build/smrnmi/klee/io \
    --out=reports/smrnmi-$(date +'%Y-%m-%d')
