#!/bin/sh

for exe in build/klee/tests/*; do
    echo $exe
    ./build/qemu/qemu-riscv32 -cpu rv32i $exe
    echo $?
done
