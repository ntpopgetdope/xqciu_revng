#!/bin/sh

inst_dir=$1
klee_dir=$2

klee_io=${klee_dir}/io
klee_tests=${klee_dir}/tests


[ ! -d ${klee_tests} ] && mkdir ${klee_tests}

for file in ${klee_dir}/*.cpp; do
    no_ext=${file%.*}
    basename=${no_ext##*/}

    echo "    - Assembling test ${klee_io}/${basename}"
    python scripts/assemble.py --inst-dir ${inst_dir} --inst-name ${basename} --io-file ${klee_io}/${basename} --out ${klee_tests}/${basename}
    chmod +x ${klee_tests}/${basename}-*
done
