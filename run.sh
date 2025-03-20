#!/bin/sh

clangpp=$1
klee=$2
rudb_dir=$3
llvm_config=$4
klee_bc=build/klee/bc
klee_out=build/klee/out
klee_exes=build/klee/exes
klee_io=build/klee/io
klee_tests=build/klee/tests
klee_tests=build/klee/tests
xqci_inst_dir=${rudb_dir}/arch_overlay/qc_iu/inst/Xqci
xqci_csr_dir=${rudb_dir}/arch_overlay/qc_iu/csr/Xqci
base_csr_dir=${rudb_dir}/arch/csr

[ ! -d build ] && mkdir build
[ ! -d build/klee ] && mkdir build/klee
[ ! -d ${klee_bc} ] && mkdir ${klee_bc}
[ ! -d ${klee_out} ] && mkdir ${klee_out}
[ ! -d ${klee_exes} ] && mkdir ${klee_exes}
[ ! -d ${klee_io} ] && mkdir ${klee_io}
[ ! -d ${klee_tests} ] && mkdir ${klee_tests}

echo "Building helper-to-tcg:"
sh build-helper-to-tcg.sh $llvm_config

echo "Generating:"
echo "  - helper-to-tcg cpp input"
python scripts/yaml-to-cpp.py \
    --xqci-csr-dir ${xqci_csr_dir} \
    --base-csr-dir ${base_csr_dir} \
    -o build/xqciu.cpp ${xqci_inst_dir}

echo "Building CSR fields"
./scripts/csr.py --inst-dir=${xqci_inst_dir} --csr-dir=${xqci_csr_dir} --out-c=build/xqciu_csr.c --out-h=build/xqciu_csr.h

echo "Compiling helper-to-tcg input -> .ll"
$clangpp build/xqciu.cpp -emit-llvm -c -g -O3 -I include -o build/xqciu.ll

echo "Running helper-to-tcg"
./build/helper-to-tcg build/xqciu.ll \
    --output-source build/xqciu_tcg.c \
    --output-header build/xqciu_tcg.h \
    --output-enabled build/xqciu_tcg_enabled \
    --output-log build/xqciu_tcg_log \
    --tcg-global-mappings=tcg_global_mappings \
    --mmu-index-function=_mmu \
    --temp-vector-block=_vector \
    &> build/helper-to-tcg-out

echo "Generating:"
echo "  - klee cpp input"
echo "  - qemu decodetree input"
echo "  - qemu decodetree translation functions"
echo "  - qemu decodetree disas functions"
python scripts/yaml-to-cpp.py \
    --output-klee build/klee \
    --output-trans build/xqciu_trans.c.inc \
    --output-decode build/xqciu \
    --output-decode-extra-functions build/xqciu-decode-extra \
    --output-disas build/riscv-xqci \
    --input-enabled build/xqciu_tcg.h \
    --xqci-csr-dir ${xqci_csr_dir} \
    --base-csr-dir ${base_csr_dir} \
    ${xqci_inst_dir}

echo "Running klee"
for file in build/klee/*.cpp; do
    no_ext=${file%.*}
    basename=${no_ext##*/}

    echo "  ${basename}"
    echo "    - Compiling klee .cpp input -> .bc"
    $clangpp $file -emit-llvm -c -g -O0 -Xclang -disable-O0-optnone -I include -I build -o ${klee_bc}/${basename}.bc

    echo "    - Running klee"
    $klee --external-calls=all \
          --only-output-states-covering-new \
          --libc=uclibc \
          --posix-runtime \
          --use-merge \
          --output-dir=${klee_out}/${basename} \
          ${klee_bc}/${basename}.bc \
          &> build/klee-out

    echo "    - Compiling test executable"
    $clangpp $file -lkleeRuntest -I include -I build -o ${klee_exes}/${basename}

    for test in ${klee_out}/${basename}/*.ktest; do
        echo "    - Collecting test ${test}"
        KTEST_FILE=$test ./${klee_exes}/${basename} >> ${klee_io}/${basename}
    done
done

echo "Assembling tests"
sh assemble-tests.sh ${xqci_inst_dir}

./scripts/decodetree-disas.py --static-decode='decode_xqci_16_impl' build/xqciu-16.decode --insnwidth=16 > build/riscv-xqci-16-decode.c.inc
./scripts/decodetree-disas.py --static-decode='decode_xqci_32_impl' build/xqciu-32.decode --insnwidth=32 > build/riscv-xqci-32-decode.c.inc
./scripts/decodetree-disas.py --static-decode='decode_xqci_48_impl' build/xqciu-48.decode --varinsnwidth=64 > build/riscv-xqci-48-decode.c.inc
