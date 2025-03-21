#!/bin/sh

inst_dir=$1

klee_io=build/klee/io
klee_tests=build/klee/tests

for file in build/klee/*.cpp; do
    no_ext=${file%.*}
    basename=${no_ext##*/}

    echo "    - Assembling test ${klee_io}/${basename}"
    python scripts/assemble.py --inst-dir ${inst_dir} --inst-name ${basename} --io-file ${klee_io}/${basename} --out ${klee_tests}/${basename}
    chmod +x ${klee_tests}/${basename}-*
done
