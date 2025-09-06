## Usage

```
$ python yaml-to-cpp.py inst -o out.cpp
$ clang14 out.cpp -O0 -Xclang -disable-O0-optnone -S -emit-llvm
$ helper-to-tcg out.ll
```

## Context

### [Automatic Frontend Generation for RISC V Extensions](https://pretalx.com/kvm-forum-2025/talk/BL3UAH/)

QEMU is an extremely useful tool during testing and development of new architectures, yet adding support for new targets is error prone and incurs a significant entry cost in terms of learning QEMU internals. Especially so when keeping up with [an evolving ISA specification](https://github.com/quic/riscv-unified-db/commits/main).

We present our methodology for rapidly implementing and testing Qualcomms [qc_iu](https://github.com/riscv-software-src/riscv-unified-db/tree/main/spec/custom/isa/qc_iu) set of RISC V extensions, in the absence of a compiler toolchain. As a first step, C++ code and later LLVM IR was produced from instruction definitions provided by [riscv-unified-db](https://github.com/riscv-software-src/riscv-unified-db). Secondly, the LLVM based `helper-to-tcg` tool was used to generate TCG implementations for [143/172 instructions](https://github.com/revng/qemu-upstream/tree/feature/xqci-v1.1/target/riscv/xqci). Usage of `helper-to-tcg` enables a emulator-in-the-loop process of designing instruction set extensions, good for rapid prototyping, validation and design space exploration

Automatic generation of per-instruction tests covering memory operations, branches, and corner cases, was accomplished with the LLVM IR based symbolic execution engine KLEE. All in all, [289 tests](https://github.com/revng/qemu-upstream/tree/feature/xqci-v1.1/tests/tcg/riscv32) were generated covering 143 instructions, for each version of the ISA specification. This proved incredibly useful in finding bugs in the original instruction definitions.

This is a follow up to our [2023 KVM forum talk](https://youtu.be/Gwz0kp7IZPE), where we successfully applied `helper-to-tcg` to the [Hexagon](https://github.com/quic/qemu/tree/hex-next/target/hexagon) frontend. Since then, the tool has evolved significantly, allowing it to be applied in more general settings.

### [helper-to-tcg](https://github.com/revng/qemu-upstream/tree/feature/helper-to-tcg-develop/subprojects/helper-to-tcg)
`helper-to-tcg` is a standalone LLVM IR to TCG translator, with the goal of simplifying the implementation of complicated instructions in TCG. Instruction semantics can be specified either directly in LLVM IR or any language that can be compiled to it (C, C++, ...). However, the tool is tailored towards QEMU helper functions written in C.

Internally, `helper-to-tcg` consists of a mix of custom and built-in transformation and analysis passes that are applied to the input LLVM IR sequentially. The pipeline of passes is laid out as follows:
```
           +---------------+    +-----+    +---------------+    +------------+
LLVM IR -> | PrepareForOpt | -> | -Os | -> | PrepareForTcg | -> | TcgGenPass | -> TCG
           +---------------+    +-----+    +---------------+    +------------+
```
where the custom passes performs:
* `PrepareForOpt` - Early culling of unneeded functions, mapping of function annotations, removal of `noinline` added by `-O0`
* `PrepareForTcg` - Post-optimization pass; gets IR as close to Tinycode as possible, goal of taking complexity away from backend
* `TcgGenPass` - Backend pass that allocates TCG variables to LLVM values, and emits final TCG C code

## References
**rev.ng**
- [KVM Forum '23 - Automatic Promotion of Helper Functions to TCG using LLVM](https://github.com/ntpopgetdope/xqciu_revng/blob/devel/docs/revng/anjo-ale-kvm-23_auto-helper2tcg-promotion-llvm-qemu.pdf)
- [September '24 - RISC-V & Hexagon Qualcomm Presentation (helper-to-tcg)](https://github.com/ntpopgetdope/xqciu_revng/blob/devel/docs/revng/ale-qcom-hexagon-idef-riscv-helper2tcg-presentation.pdf)
- [KVM Forum '25 - Automatic Frontend Generation for RISC V Extensions](https://github.com/ntpopgetdope/xqciu_revng/blob/devel/docs/revng/anjo-kvm-25_automatic-frontend-generation-xqci-exts.pdf)

**qcom**
- [RISC-V UnifiedDB SIG - Introduction to riscv-unified-db (UDB)](https://github.com/ntpopgetdope/xqciu_revng/blob/devel/docs/qcom/dhower_riscv-unified-db.pdf)
- [FOSDEM '25 - RISC-V udb Streamlining the Ecosystem](https://github.com/ntpopgetdope/xqciu_revng/blob/devel/docs/qcom/afonso-fosdem25_riscv-unified-db.pdf)
- [Qualcomm uC RISC-V Extensions (qc_iu)](https://github.com/ntpopgetdope/xqciu_revng/blob/devel/docs/qcom/xqci_extension-0.13.0.pdf)
- [Qualcomm RISC-V ELF psABI Extensions](https://github.com/ntpopgetdope/xqciu_revng/blob/devel/docs/qcom/riscv-elf-psabi-quic-extensions-v0.2.pdf)