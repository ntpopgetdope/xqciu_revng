#!/usr/bin/env python3

import yaml
import argparse
import re
import subprocess
import os
import math
from copy import deepcopy
import common

re_comment_find    = re.compile(r".*#.*$")
re_comment_replace = re.compile(r"")

str_includes = """
#include <stdint.h>
#include <stddef.h>
#include <initializer_list>
#include <iterator>
#include "tcg_global_mappings.h"
"""

str_memory_funcs = """
struct CPUArchState;
using abi_ptr = uint32_t;

uint32_t cpu_ldub_data(CPUArchState *env, abi_ptr ptr);
uint32_t cpu_lduw_le_data(CPUArchState *env, abi_ptr ptr);
uint32_t cpu_ldl_le_data(CPUArchState *env, abi_ptr ptr);
uint64_t cpu_ldq_le_data(CPUArchState *env, abi_ptr ptr);

void cpu_stb_data(CPUArchState *env, abi_ptr ptr, uint32_t val);
void cpu_stw_le_data(CPUArchState *env, abi_ptr ptr, uint32_t val);
void cpu_stl_le_data(CPUArchState *env, abi_ptr ptr, uint32_t val);
void cpu_stq_le_data(CPUArchState *env, abi_ptr ptr, uint64_t val);

template<int N> void write_memory(XReg va, XReg value, uint32_t encoding = 0);
template<> void write_memory<8>(XReg va, XReg value, uint32_t encoding)  { cpu_stb_data(NULL, va.value, value.value); }
template<> void write_memory<16>(XReg va, XReg value, uint32_t encoding) { cpu_stw_le_data(NULL, va.value, value.value); }
template<> void write_memory<32>(XReg va, XReg value, uint32_t encoding) { cpu_stl_le_data(NULL, va.value, value.value); }

template<int N> XReg read_memory(XReg va, uint32_t encoding = 0);
template<> XReg read_memory<8>(XReg va, uint32_t encoding)  { return cpu_ldub_data(NULL, va.value); }
template<> XReg read_memory<16>(XReg va, uint32_t encoding) { return cpu_lduw_le_data(NULL, va.value); }
template<> XReg read_memory<32>(XReg va, uint32_t encoding) { return cpu_ldl_le_data(NULL, va.value); }
"""

str_memory_funcs_klee = """
#include <unordered_map>
#include <assert.h>

static bool has_jump = false;
static bool has_valid_test_jump = false;
static int jump_pc_offset = 0;
static std::unordered_map<uint32_t, uint32_t> memory;

template<int N> void write_memory(XReg va, XReg value, uint32_t encoding = 0);
template<> void write_memory<8>(XReg va, XReg value, uint32_t encoding)  { memory[va.value] = value.value & 0xff; }
template<> void write_memory<16>(XReg va, XReg value, uint32_t encoding) { memory[va.value] = value.value & 0xffff; }
template<> void write_memory<32>(XReg va, XReg value, uint32_t encoding) { memory[va.value] = value.value & 0xffffffff;}

template<int N> XReg read_memory(XReg va, uint32_t encoding = 0);
template<> XReg read_memory<8>(XReg va, uint32_t encoding)  { return memory[va.value]; }
template<> XReg read_memory<16>(XReg va, uint32_t encoding) { return memory[va.value]; }
template<> XReg read_memory<32>(XReg va, uint32_t encoding) { return memory[va.value]; }

void xqci_jump_pcrel(XReg pc, int imm) {
    has_jump = true;
    jump_pc_offset = imm;
    if (imm == INST_SIZE + 4) {
        has_valid_test_jump = true;
    }
}

#define DEF_SEXTRACT(size)                                                                      \
    static int ## size ## _t sextract ## size(uint ## size ## _t value, int start, int length)  \
    {                                                                                           \
        assert(start >= 0 && length > 0 && length <= size - start);                             \
        return ((int ## size ## _t)(value << (size - length - start))) >> (size - length);      \
    }

DEF_SEXTRACT(8)
DEF_SEXTRACT(16)
DEF_SEXTRACT(32)
DEF_SEXTRACT(64)

"""

str_reg_structs = """
constexpr size_t xlen() {
    return 32;
}

//struct BitModifier {
//    uint32_t &i;
//    uint32_t bit;
//
//    BitModifier(uint32_t &i, uint32_t bit)
//      : i(i), bit(bit) {}
//
//    uint32_t mask() const {
//        return 1 << bit;
//    }
//
//    uint32_t get_bit() const {
//        return (i >> bit) & 1;
//    }
//
//    BitModifier &operator=(const BitModifier &m) {
//        i = (i & ~m.mask()) | (m.i & m.mask());
//        return *this;
//    }
//
//    operator uint32_t() const {
//        return get_bit();
//    }
//};

struct XRegRange {
    uint32_t value;
    uint32_t length;

    XRegRange(uint32_t value, uint32_t length = 1)
        : value(value), length(length) {}

    //XRegRange(BitModifier m)
    //    : XRegRange(m.get_bit()) {}

    operator uint32_t() const {
        return value;
    }
};

//template<int N>
//struct __attribute__((packed)) Bits {
//    uint32_t value;
//
//    Bits(uint32_t value = 0) : value(value) {}
//    Bits(std::initializer_list<XRegRange> ranges)
//        : value(0) {
//        size_t offset = 0;
//        for (auto it = std::rbegin(ranges); it != std::rend(ranges); ++it) {
//          value |= (it->value << offset);
//          offset += it->length;
//        }
//    }
//    template<int M>
//    Bits(Bits<M> bits)
//        : value(bits.value & ((1ul << N)-1)) {
//    }
//    Bits(XRegRange range)
//        : value(range.value & ((1ul << range.length)-1)) {
//    }
//
//    explicit operator bool() const {
//        return value != 0;
//    }
//
//    BitModifier operator[](size_t i) {
//        return BitModifier(value, (uint32_t)i);
//    }
//
//    BitModifier operator[](Bits<N> reg) {
//        return BitModifier(value, reg.value);
//    }
//
//    XRegRange range(size_t b, size_t e) {
//        uint32_t mask = ((uint32_t) -1) >> (31 - e);
//        return XRegRange((value & mask) >> b, e-b+1);
//    }
//};

template<int N>
struct __attribute__((packed)) Bits {
    uint32_t value;

    Bits(uint32_t value = 0) : value(value) {}
    Bits(std::initializer_list<XRegRange> ranges)
        : value(0) {
        size_t offset = 0;
        for (auto it = std::rbegin(ranges); it != std::rend(ranges); ++it) {
          value |= (it->value << offset);
          offset += it->length;
        }
    }
    template<int M>
    Bits(Bits<M> bits)
        : value(bits.value & ((1ul << N)-1)) {
    }
    Bits(XRegRange range)
        : value(range.value & ((1ul << range.length)-1)) {
    }

    explicit operator bool() const {
        return value != 0;
    }

    uint32_t operator[](size_t i) {
        return (value >> i) & 1;
    }

    uint32_t operator[](Bits<N> reg) {
        return (value >> reg.value) & 1;
    }

    XRegRange range(size_t b, size_t e) {
        uint32_t mask = ((uint32_t) -1) >> (31 - e);
        return XRegRange((value & mask) >> b, e-b+1);
    }
};

using XReg = Bits<32>;
using U32 = Bits<32>;

uint32_t sext(const XReg &i, const XReg len) {
    return ((int32_t) (i.value << (32-len.value))) >> (32-len.value);
}

uint32_t highest_set_bit(const XReg &i) {
    return 31 - __builtin_clz(i.value);
}

uint32_t lowest_set_bit(const XReg &i) {
    return 1 + __builtin_ctz(i.value);
}

struct CSRReg {
    uint32_t value;
    uint32_t NMI;
    uint32_t MIE;
    uint32_t MPIE;
    uint32_t MPP;
    uint32_t MPRV;

    CSRReg(uint32_t value = 0) : value(value) {}

    explicit operator bool() const {
        return value != 0;
    }

    uint32_t operator[](size_t i) {
        return (value >> i) & 1;
    }

    Bits<12> address() {
        return {value};
    }

    XReg sw_read() {
        return XReg(value);
    }

    void sw_write(XReg reg) {
        value = reg.value;
    }
};

__attribute__((annotate ("immediate: 1")))
void xqci_jump_pcrel(XReg pc, int imm);

struct XRegSet {
    XReg regs[32];

    XRegSet() {}

    XReg &operator[](size_t i) {
        return regs[i];
    }

    XReg &operator[](XReg reg) {
        return regs[reg.value];
    }
};

struct CSRRegSet {
    CSRReg regs[32];

    CSRRegSet() {}

    CSRReg &operator[](size_t i) {
        return regs[i];
    }

    CSRReg &operator[](XReg reg) {
        return regs[reg.value];
    }
};
"""

str_operators = """
XReg operator^(const XReg &a, const XReg &b) { return XReg(a.value ^ b.value); }
XReg operator+(XReg a, XReg b) { return XReg(a.value + b.value); }
XReg operator-(const XReg &a, const XReg &b) { return XReg(a.value - b.value); }
XReg operator*(const XReg &a, const XReg &b) { return XReg(a.value * b.value); }
XReg operator/(const XReg &a, const XReg &b) { return XReg(a.value / b.value); }
XReg operator%(const XReg &a, const XReg &b) { return XReg(a.value % b.value); }
XReg operator&(const XReg &a, const XReg &b) { return XReg(a.value & b.value); }
XReg operator|(const XReg &a, const XReg &b) { return XReg(a.value | b.value); }
XReg operator>>(const XReg &a, const XReg &b) { return XReg(a.value >> b.value); }
XReg operator<<(const XReg &a, const XReg &b) { return XReg(a.value << b.value); }
XReg operator-(const XReg &a) { return XReg(-a.value); }
XReg operator~(const XReg &a) { return XReg(~a.value); }
XReg operator++(XReg &a, int) {
    XReg tmp = a;
    a.value++;
    return a;
}

bool operator>(const XReg &a, const XReg &b) { return a.value > b.value; }
bool operator>=(const XReg &a, const XReg &b) { return a.value >= b.value; }
bool operator==(const XReg &a, const XReg &b) { return a.value == b.value; }
bool operator<=(const XReg &a, const XReg &b) { return a.value <= b.value; }
bool operator<(const XReg &a, const XReg &b) { return a.value < b.value; }
bool operator!=(const XReg &a, const XReg &b) { return a.value != b.value; }
"""

str_klee_operators = """
bool overflow = false;
bool underflow = false;

#define OP_CHECK_WRAP(op,a,b)                           \
    do {                                                \
        int64_t res = ((int64_t) a) op ((int64_t) b);   \
        if (res > UINT32_MAX) {                         \
            overflow = true;                            \
        }                                               \
        if (res < 0) {                                  \
            underflow = true;                           \
        }                                               \
    } while(0)

XReg operator^(const XReg &a, const XReg &b) { return XReg(a.value ^ b.value); }
XReg operator+(XReg a, XReg b) {
    OP_CHECK_WRAP(+, a.value, b.value);
    return XReg(a.value + b.value);
}
XReg operator-(const XReg &a, const XReg &b) {
    OP_CHECK_WRAP(-, a.value, b.value);
    return XReg(a.value - b.value);
}
XReg operator*(const XReg &a, const XReg &b) {
    OP_CHECK_WRAP(*, a.value, b.value);
    return XReg(a.value * b.value);
}
XReg operator/(const XReg &a, const XReg &b) { return XReg(a.value / b.value); }
XReg operator%(const XReg &a, const XReg &b) { return XReg(a.value % b.value); }
XReg operator&(const XReg &a, const XReg &b) { return XReg(a.value & b.value); }
XReg operator|(const XReg &a, const XReg &b) { return XReg(a.value | b.value); }
XReg operator>>(const XReg &a, const XReg &b) { return XReg(a.value >> b.value); }
XReg operator<<(const XReg &a, const XReg &b) {
    OP_CHECK_WRAP(<<, a.value, b.value);
    return XReg(a.value << b.value);
}
XReg operator-(const XReg &a) { return XReg(-a.value); }
XReg operator~(const XReg &a) { return XReg(~a.value); }
XReg operator++(XReg &a, int) {
    XReg tmp = a;
    a.value++;
    return a;
}

bool operator>(const XReg &a, const XReg &b) { return a.value > b.value; }
bool operator>=(const XReg &a, const XReg &b) { return a.value >= b.value; }
bool operator==(const XReg &a, const XReg &b) { return a.value == b.value; }
bool operator<=(const XReg &a, const XReg &b) { return a.value <= b.value; }
bool operator<(const XReg &a, const XReg &b) { return a.value < b.value; }
bool operator!=(const XReg &a, const XReg &b) { return a.value != b.value; }
"""

preamble = """
enum class PrivilegeMode {
    S, U, M
};

enum class ExtensionName {
    S, U
};

void set_mode(const PrivilegeMode m) {
}

bool implemented(const ExtensionName n) {
    return true;
}

struct CPUArchState {
    static constexpr uint32_t qc_mclicie0 = 0;
    static constexpr uint32_t qc_mclicie1 = 1;
    static constexpr uint32_t qc_mclicie2 = 2;
    static constexpr uint32_t qc_mclicie3 = 3;
    static constexpr uint32_t qc_mclicie4 = 4;
    static constexpr uint32_t qc_mclicie5 = 5;
    static constexpr uint32_t qc_mclicie6 = 6;
    static constexpr uint32_t qc_mclicie7 = 7;
    static constexpr uint32_t qc_mclicip0 = 8;
    static constexpr uint32_t qc_mclicip1 = 9;
    static constexpr uint32_t qc_mclicip2 = 10;
    static constexpr uint32_t qc_mclicip3 = 11;
    static constexpr uint32_t qc_mclicip4 = 12;
    static constexpr uint32_t qc_mclicip5 = 13;
    static constexpr uint32_t qc_mclicip6 = 14;
    static constexpr uint32_t qc_mclicip7 = 15;
    static constexpr uint32_t mstatus  = 16;
    static constexpr uint32_t mcause   = 17;
    static constexpr uint32_t mncause  = 18;
    static constexpr uint32_t mepc     = 19;
    static constexpr uint32_t qc_mnepc    = 20;
    static constexpr uint32_t qc_flags    = 21;

    static constexpr uint32_t XLEN     = 32;

    inline int32_t _signed(XReg reg) {
        return (int32_t) reg.value;
    }

    inline void delay(uint8_t) {
    }

    XRegSet X;
    XReg pc;
    CSRRegSet CSR;

    CPUArchState() {}
"""

manual_shlsat = """
__attribute__((used))
__attribute__((annotate ("immediate: 1, 2, 3")))
__attribute__((annotate ("helper-to-tcg")))
void qc_shlsat(uint8_t rs1, uint8_t rs2, uint8_t rd) {
    int64_t sext_double_width_rs1 = ((int64_t)(int32_t)X[rs1].value);
    int64_t shifted_value = sext_double_width_rs1 << X[rs2].range(0, 4);
    XReg most_negative_number = 1 << (xlen() - 1);
    XReg most_positive_number = (1 << (xlen() - 1)) - 1;
    
    if ((int64_t)(shifted_value) < (int64_t)(int32_t)(most_negative_number.value)) {
      X[rd] = most_negative_number;
    } else if ((int64_t)(shifted_value) > (int64_t)(int32_t)(most_positive_number.value)) {
      X[rd] = most_positive_number;
    } else {
      X[rd] = (uint32_t)shifted_value;
    }
}
"""
manual_shlusat = """
__attribute__((used))
__attribute__((annotate ("immediate: 1, 2, 3")))
__attribute__((annotate ("helper-to-tcg")))
void qc_shlusat(uint8_t rs1, uint8_t rs2, uint8_t rd) {
    int64_t sext_double_width_rs1 = ((int64_t)(int32_t)X[rs1].value);
    int64_t shifted_value = sext_double_width_rs1 << X[rs2].range(0, 4);
    XReg largest_unsigned_value = ~0u;
    
    if (shifted_value > largest_unsigned_value.value) {
      X[rd] = largest_unsigned_value;
    } else {
      X[rd] = (uint32_t)shifted_value;
    }
}
"""

manual_impls = {
    'qc.shlsat.yaml' : manual_shlsat,
    'qc.shlusat.yaml' : manual_shlusat
}

postamble = """
struct TCGv {};
TCGv cpu_gpr[32];
TCGv cpu_pc;
__attribute__((used))
cpu_tcg_mapping tcg_global_mappings[] = {
    cpu_tcg_map_array(CPUArchState, cpu_gpr, X, NULL),
    cpu_tcg_map(CPUArchState, cpu_pc, pc, NULL)
};
"""

def should_decode_only(name):
    return name in common.decode_only

def should_translate(name):
    return name in {
        #'qc.addsat.yaml',
        'qc.addusat.yaml',
        'qc.beqi.yaml',
        'qc.bgei.yaml',
        'qc.bgeui.yaml',
        'qc.blti.yaml',
        'qc.bltui.yaml',
        'qc.bnei.yaml',
        #'qc.brev32.yaml',
        'qc.c.bexti.yaml',
        'qc.c.bseti.yaml',
        'qc.c.clrint.yaml',
        'qc.c.dir.yaml',
        'qc.c.di.yaml',
        'qc.c.eir.yaml',
        'qc.c.ei.yaml',
        'qc.c.extu.yaml',
        'qc.clo.yaml',
        'qc.clrinti.yaml',
        #'qc.c.mienter.nest.yaml',
        #'qc.c.mienter.yaml',
        #'qc.c.mileaveret.yaml',
        #'qc.c.mnret.yaml',
        #'qc.c.mret.yaml',
        'qc.c.muliadd.yaml',
        'qc.muliadd.yaml',
        #'qc.c.mveqz.yaml',
        'qc.compress2.yaml',
        'qc.compress3.yaml',
        'qc.c.setint.yaml',
        #'qc.csrrwri.yaml',
        #'qc.csrrwr.yaml',
        'qc.cto.yaml',
        'qc.e.addai.yaml',
        'qc.e.addi.yaml',
        'qc.e.andai.yaml',
        'qc.e.andi.yaml',
        'qc.e.beqi.yaml',
        'qc.e.bgei.yaml',
        'qc.e.bgeui.yaml',
        'qc.e.blti.yaml',
        'qc.e.bltui.yaml',
        'qc.e.bnei.yaml',
        'qc.e.jal.yaml',
        'qc.e.j.yaml',
        'qc.e.lbu.yaml',
        'qc.e.lb.yaml',
        'qc.e.lhu.yaml',
        'qc.e.lh.yaml',
        'qc.e.li.yaml',
        'qc.e.lw.yaml',
        'qc.e.orai.yaml',
        'qc.e.ori.yaml',
        'qc.e.sb.yaml',
        'qc.e.sh.yaml',
        'qc.e.sw.yaml',
        'qc.e.xorai.yaml',
        'qc.e.xori.yaml',
        'qc.expand2.yaml',
        'qc.expand3.yaml',

        'qc.extdprh.yaml',
        'qc.extdpr.yaml',
        'qc.extdr.yaml',
        'qc.extduprh.yaml',
        'qc.extdupr.yaml',
        'qc.extdur.yaml',
        'qc.extdu.yaml',
        'qc.extd.yaml',

        'qc.extu.yaml',
        'qc.ext.yaml',

        'qc.insbhr.yaml',
        'qc.insbh.yaml',
        'qc.insbi.yaml',
        'qc.insbprh.yaml',
        'qc.insbpr.yaml',
        'qc.insbri.yaml',
        'qc.insbr.yaml',

        'qc.insb.yaml',
        'qc.lieqi.yaml',
        'qc.lieq.yaml',
        'qc.ligei.yaml',
        'qc.ligeui.yaml',
        'qc.ligeu.yaml',
        'qc.lige.yaml',
        'qc.lilti.yaml',
        'qc.liltui.yaml',
        'qc.liltu.yaml',
        'qc.lilt.yaml',
        'qc.linei.yaml',
        'qc.line.yaml',
        'qc.li.yaml',
        'qc.lrbu.yaml',
        'qc.lrb.yaml',
        'qc.lrhu.yaml',
        'qc.lrh.yaml',
        'qc.lrw.yaml',

        'qc.muladdi.yaml',
        'qc.mveqi.yaml',
        'qc.mveq.yaml',
        'qc.mvgei.yaml',
        'qc.mvgeui.yaml',
        'qc.mvgeu.yaml',
        'qc.mvge.yaml',
        'qc.mvlti.yaml',
        'qc.mvltui.yaml',
        'qc.mvltu.yaml',
        'qc.mvlt.yaml',
        'qc.mvnei.yaml',
        'qc.mvne.yaml',
        'qc.normeu.yaml',
        'qc.normu.yaml',
        'qc.norm.yaml',
        #'qc.selecteqi.yaml',
        'qc.selectieqi.yaml',
        'qc.selectieq.yaml',
        'qc.selectiieq.yaml',
        'qc.selectiine.yaml',
        'qc.selectinei.yaml',
        'qc.selectine.yaml',
        #'qc.selectnei.yaml',
        'qc.setinti.yaml',
        'qc.shladd.yaml',
        #'qc.shlsat.yaml',
        #'qc.shlusat.yaml',
        'qc.srb.yaml',
        'qc.srh.yaml',
        'qc.srw.yaml',
        #'qc.subsat.yaml',
        'qc.subusat.yaml',
        'qc.wrapi.yaml',
        'qc.wrap.yaml'
    }

def round_to_power_of_two(x):
    return int(2**math.ceil(math.log2(x)))

def bit_to_c_size(x):
    return min(max(round_to_power_of_two(x), 8), 64)

def var_size_from_location(loc_str):
    sum = 0
    for _,length in common.ranges_in_location(loc_str):
        sum += length
    return sum

def find_var_by_loc(y, loc):
    if 'variables' in y:
        for v in y['variables']:
            if v['location'] == loc:
                return v
    return None

def write_line(f, indent, str):
    for i in range(0,indent):
        f.write(' ')
    f.write(str)
    f.write('\n')

def emit_type(f, y, inst, instructions):
    base_variables = y['variables'] if 'variables' in y else []
    for i in inst:
        variables = instructions[i]['variables'] if 'variables' in instructions[i] else []
        write_line(f, 0, 'typedef struct {')
        for v0 in base_variables:
            name = f"unused_{v0['name']}"
            for v1 in variables:
                if v1['location'] == v0['location']:
                    name = v1['name']
            write_line(f, 4, f"int {name};")
        write_line(f, 0, f'}} arg_{i};')

def emit_switch(f, y, count, defaults, depth):
    indent = 4*(depth+1)
    for loc in count:
        fields = count[loc]
        if len(fields) == 0:
            continue
        a = find_var_by_loc(y, loc)
        write_line(f, indent, f"switch(arg->{a['name']}) {{")

        for field in fields:
            write_line(f, indent, f'case {int(field,2)}:')
            if isinstance(fields[field], set):
                for func in fields[field]:
                    write_line(f, indent+4, f'trans_{func}(ctx, (arg_{func} *) arg);')
            else:
                emit_switch(f, y, fields[field], defaults, depth+1)
            write_line(f, indent+4, 'break;')

        if loc in defaults:
            write_line(f, indent, 'default:')
            write_line(f, indent+4, f'trans_{defaults[loc]}(ctx, (arg_{defaults[loc]} *) arg);')

        write_line(f, indent, '}')

def main():
    parser = argparse.ArgumentParser(
        prog='yaml-to-cpp',
        description='Convert Xqciu instruction definitions from yaml to cpp'
    )
    parser.add_argument('file')
    parser.add_argument('-o', '--out')
    parser.add_argument('--output-decode')
    parser.add_argument('--output-decode-extra-functions')
    parser.add_argument('--output-trans')
    parser.add_argument('--output-klee')
    parser.add_argument('--output-disas')
    parser.add_argument('--input-enabled')
    args = parser.parse_args()

    if args.output_trans:
        with open(args.output_trans, 'w') as out:
            translated = ''
            with open(args.input_enabled, 'r') as in_enabled:
                translated = in_enabled.read()
            for file in os.listdir(args.file):
                if not should_translate(file) and not should_decode_only(file):
                    continue

                with open(os.path.join(args.file, file), 'r') as f:
                    try:
                        y = yaml.safe_load(f)
                        name = y['name']
                        op_name = re.sub(r'\.', r'_', name)
                        #if len(translated) > 0 and not op_name in translated:
                        #    continue
                        out.write(f'static bool trans_{op_name}(DisasContext *ctx, arg_{op_name} *arg)\n')
                        out.write('{\n')

                        str_args = []
                        if 'variables' in y['encoding']:
                            str_args = [f"arg->{v['name']}" for v in y['encoding']['variables']]
                            for v in y['encoding']['variables']:

                                # TODO: Order?

                                if 'not' in v:
                                    not_values = v['not'] if isinstance(v['not'], list) else [v['not']]
                                    conditions = [f"arg->{v['name']} == {n}" for n in not_values]
                                    out.write(f"    if ({' || '.join(conditions)}) {{\n")
                                    out.write( "        return false;\n")
                                    out.write( "    }\n")
                                if 'left_shift' in v:
                                    out.write(f"    arg->{v['name']} <<= {v['left_shift']};\n")

                        out.write(f'    emit_{op_name}(ctx, tcg_env')
                        if len(str_args) > 0:
                            out.write(', ')
                            out.write(', '.join(str_args))
                        out.write(');\n')

                        if 'jump_halfword' in y['operation()']:
                            out.write('    gen_goto_tb(ctx, 0, ctx->cur_insn_len);\n');

                        out.write('    return true;\n')
                        out.write('}\n')

                    except yaml.YAMLError as e:
                        print(e)

    if args.output_decode:
        translated = ''
        with open(args.input_enabled, 'r') as in_enabled:
            translated = in_enabled.read()
        defs = {}
        formats = {}

        encoding = {}
        operation = {}
        for file in os.listdir(args.file):
            if not should_translate(file) and not should_decode_only(file):
                continue
            with open(os.path.join(args.file, file), 'r') as f:
                try:
                    y = yaml.safe_load(f)
                    name = y['name']
                    op_name = re.sub(r'\.', r'_', name)
                    #if len(translated) > 0 and not op_name in translated:
                    #    continue
                    encoding[op_name] = y['encoding']
                    operation[op_name] = y['operation()']
                except yaml.YAMLError as e:
                    print(e)

        instruction_sizes = {}
        for name in encoding:
            size = len(encoding[name]['match'])
            if not size in instruction_sizes:
                instruction_sizes[size] = []
            instruction_sizes[size].append(name)

        # Look for instructions with the same width whose fixed bit patterns
        # overlap.
        for size in instruction_sizes:
            new_inst = {}
            overlapping = []

            N = len(instruction_sizes[size])
            for i0 in range(0, N):
                n0 = instruction_sizes[size][i0]
                fixed0 = encoding[n0]['match']
                p0 = int(re.sub(r'-', r'0', fixed0), 2)
                for i1 in range(i0+1, N):
                    n1 = instruction_sizes[size][i1]
                    fixed1 = encoding[n1]['match']
                    p1 = int(re.sub(r'-', r'0', fixed1), 2)

                    matches = True
                    for j in range(0,size):
                        rj = size-1 - j
                        if fixed0[rj] == '1' and fixed1[rj] == '0' or \
                           fixed0[rj] == '0' and fixed1[rj] == '1':
                            matches = False
                            break

                    if matches:
                        inserted = False
                        for o in overlapping:
                            if n0 in o:
                                o.add(n1)
                                inserted = True
                                break
                            if n1 in o:
                                o.add(n0)
                                inserted = True
                                break
                        if not inserted:
                            overlapping.append({n0, n1})

                    if p0 == p1:
                        new_name = f'{n0}_{n1}'
                        new_inst[new_name] = [n0, n1]

            for o in overlapping:
                for e in o:
                    instruction_sizes[size].remove(e)
                instruction_sizes[size].append(o)

        for size in instruction_sizes:
            for inst in instruction_sizes[size]:
                y = None
                inst_name = None

                group_formats = []

                if not size in defs:
                    defs[size] = {}

                if not size in formats:
                    formats[size] = []

                if isinstance(inst, set):
                    for i in inst:
                        inst_name = i

                        vars = []
                        pattern = encoding[i]['match']
                        pattern = re.sub(r'([-]+)', r' \1 ', pattern)
                        pattern = re.sub(r'-', r'.', pattern)

                        format = f"{inst_name} {pattern}"

                        if 'variables' in encoding[i]:
                            for v in encoding[i]['variables']:
                                ranges = []
                                names = []

                                for r in v['location'].split('|'):
                                    if '-' in r:
                                        offsets = [int(s) for s in r.split('-')]
                                        start = offsets[1]
                                        length = offsets[0] - offsets[1] + 1
                                    else:
                                        offset = int(r)
                                        length = 1
                                        start = offset

                                    start += round_to_power_of_two(size) - size
                                    ranges.append(f'{start}:{length}')
                                    names.append(f'{start}_{length}')

                                name = f"{v['name']}_{'_'.join(names)}"
                                defs[size][name] = f"%{name} {' '.join(ranges)}"
                                format = format + f" {v['name']}=%{name}"

                        group_formats.append(format)

                    formats[size].append(group_formats)

        for size in instruction_sizes:
            combined_instructions = []
            for inst in instruction_sizes[size]:
                if isinstance(inst, set):
                    continue

                y = encoding[inst]
                inst_name = inst

                vars = []
                pattern = y['match']
                pattern = re.sub(r'([-]+)', r' \1 ', pattern)
                pattern = re.sub(r'-', r'.', pattern)

                if not size in defs:
                    defs[size] = {}

                if not size in formats:
                    formats[size] = []

                format = f"{inst_name} {pattern}"

                if 'variables' in y:
                    for v in y['variables']:
                        ranges = []
                        names = []

                        # Sanity check
                        for subfield in v:
                            if subfield not in {
                                    'name',
                                    'not',
                                    'location',
                                    'sign_extend',
                                    'left_shift' # left shift is handled in trans_*()
                                }:
                                print(f'Unhandled field in variable {subfield}')
                                assert(False)

                        for i,r in enumerate(common.ranges_in_location(v['location'])):
                            start,length = r

                            sign_extend = ''
                            if i == 0 and 'sign_extend' in v:
                                assert(v['sign_extend'] == True)
                                sign_extend = 's'

                            start += round_to_power_of_two(size) - size
                            ranges.append(f'{start}:{sign_extend}{length}')
                            names.append(f'{start}_{length}')

                        name = f"{v['name']}_{'_'.join(names)}"
                        defs[size][name] = f"%{name} {' '.join(ranges)}"
                        format = format + f" {v['name']}=%{name}"

                formats[size].append(format)

            for pattern_length in defs:
                with open(f'{args.output_decode}-{pattern_length}.decode', 'w') as out:

                    for name in defs[pattern_length]:
                        out.write(defs[pattern_length][name])
                        out.write('\n')

                    for f in formats[pattern_length]:
                        if isinstance(f, list):
                            out.write('{\n')
                            for subf in f:
                                out.write('  ')
                                out.write(subf)
                                out.write('\n')
                            out.write('}\n')
                        else:
                            out.write(f)
                            out.write('\n')

        if args.output_disas:
            instructions = {}
            for file in os.listdir(args.file):
                if not should_translate(file) and not should_decode_only(file):
                    continue

                translated = ''
                with open(args.input_enabled, 'r') as in_enabled:
                    translated = in_enabled.read()

                y = None
                with open(os.path.join(args.file, file), 'r') as f:
                    try:
                        y = yaml.safe_load(f)
                    except yaml.YAMLError as e:
                        print(f'Error: {e}')
                        continue
                instructions[y['name']] = y

            with open(f'{args.output_disas}.h', 'w') as out:
                out.write("#ifndef DISAS_RISCV_XQCI_H\n")
                out.write("#define DISAS_RISCV_XQCI_H\n")
                out.write("\n")
                out.write("extern const rv_opcode_data xqci_opcode_data[];\n")
                out.write("void decode_xqci(rv_decode *, rv_isa);\n")
                out.write("\n")
                out.write("#endif\n")

            with open(f'{args.output_disas}.c', 'w') as out:
                out.write('#include \"qemu/osdep.h\"\n')
                out.write('#include \"qemu/bitops.h\"\n')
                out.write('#include \"disas/riscv.h\"\n')
                out.write('#include \"disas/riscv-xqci.h\"\n')
                out.write('\n')

                out.write("typedef enum {\n")
                for inst in instructions:
                    y = instructions[inst]
                    variables = y['encoding']['variables'] if 'variables' in y['encoding'] else []
                    op_name = re.sub(r'\.', r'_', y['name'])
                    out.write(f"    rv_op_{op_name},\n")
                out.write("} rv_xqci_opcode;\n")
                out.write("\n")

                out.write("const rv_opcode_data xqci_opcode_data[] = {\n")
                for inst in instructions:
                    y = instructions[inst]
                    variables = y['encoding']['variables'] if 'variables' in y['encoding'] else []
                    fmt_args = []
                    for v in reversed(variables):
                        fmt = {
                            'rd' : '0',
                            'rs1' : '1',
                            'rs2' : '2',
                            'rs3' : '6',
                            'uimm' : 'k',
                            'shamt' : 'k',
                            'shamt' : 'k',
                            'width_minus1' : 'i',
                            'imm' : 'i',
                            'simm' : 'i',
                            'simm1' : 'i',
                            'simm2' : 'i',
                            'length' : 'i',
                            'offset' : 'Z',
                        }
                        if v['name'] not in fmt:
                            print(f"Unhandled variable fmt {v['name']}")
                            print(f"For inst:");
                            print(f"{y}")
                            continue

                        fmt_args.append(fmt[v['name']])

                    fmt_str = f"O\\t{','.join(fmt_args)}"
                    name = y['name']
                    out.write(f"    {{ \"{name}\", rv_codec_skip, \"{fmt_str}\", NULL, 0, 0, 0 }},\n")
                out.write("};\n")

                out.write("\n")

                out.write('static uint64_t decode_xqci_48_impl_load_bytes(rv_decode *dec, uint64_t insn, int offset, int length)\n')
                out.write('{\n')
                out.write('    return 0;\n')
                out.write('}\n')

                out.write("#include \"riscv-xqci-16-decode.c.inc\"\n")
                out.write("#include \"riscv-xqci-32-decode.c.inc\"\n")
                out.write("#include \"riscv-xqci-48-decode.c.inc\"\n")
                out.write("#include \"riscv-xqci-trans.c.inc\"\n")
                out.write("\n");

                out.write("void decode_xqci(rv_decode *dec, rv_isa isa) {\n")
                out.write("    rv_inst inst = dec->inst;\n")
                out.write("    dec->op = rv_op_illegal;\n")
                out.write("    switch (dec->inst_length) {\n")
                out.write("    case 2:\n")
                out.write("        decode_xqci_16_impl(dec, inst);\n")
                out.write("        break;\n")
                out.write("    case 4:\n")
                out.write("        decode_xqci_32_impl(dec, inst);\n")
                out.write("        break;\n")
                out.write("    case 6:\n")
                out.write("        decode_xqci_48_impl(dec, inst << 16);\n")
                out.write("        break;\n")
                out.write("    }\n")
                out.write("}\n")

            with open(f'{args.output_disas}-trans.c.inc', 'w') as out:
                for inst in instructions:
                    y = instructions[inst]
                    name = y['name']
                    op_name = re.sub(r'\.', r'_', name)
                    #if len(translated) > 0 and not op_name in translated:
                    #    continue
                    out.write(f'static bool trans_{op_name}(rv_decode *dec, arg_{op_name} *arg)\n')
                    out.write('{\n')

                    str_args = []
                    if 'variables' in y['encoding']:
                        str_args = [f"arg->{v['name']}" for v in y['encoding']['variables']]
                        for v in y['encoding']['variables']:

                            # TODO: Order?

                            if 'not' in v:
                                not_values = v['not'] if isinstance(v['not'], list) else [v['not']]
                                conditions = [f"arg->{v['name']} == {n}" for n in not_values]
                                out.write(f"    if ({' || '.join(conditions)}) {{\n")
                                out.write( "        return false;\n")
                                out.write( "    }\n")
                            if 'left_shift' in v:
                                out.write(f"    arg->{v['name']} <<= {v['left_shift']};\n")

                        for v in y['encoding']['variables']:
                            remap_fields = {
                                'shamt' : 'uimm',
                                'width_minus1' : 'imm',
                                'simm' : 'imm',
                                'simm1' : 'imm',
                                'simm2' : 'imm',
                                'length' : 'imm',
                            }
                            field = remap_fields[v['name']] if v['name'] in remap_fields else v['name']
                            if not common.var_is_imm(y['operation()'], name) and common.inst_is_compressed(y):
                                out.write(f"    dec->{field} = arg->{v['name']} + 8;\n")
                            else:
                                out.write(f"    dec->{field} = arg->{v['name']};\n")

                    out.write(f'    dec->op = rv_op_{op_name};\n')
                    out.write( '    return true;\n')
                    out.write('}\n')

    if args.out:
        with open(args.out, 'w') as out:
            out.write(str_includes)
            out.write(str_reg_structs)
            out.write(str_operators)
            out.write(str_memory_funcs)
            out.write(preamble)
            for op in manual_impls:
                out.write(manual_impls[op])
            for file in os.listdir(args.file):
                if not should_translate(file):
                    continue

                with open(os.path.join(args.file, file), 'r') as f:
                    try:
                        y = yaml.safe_load(f)
                        vars = []
                        if 'variables' in y['encoding']:
                            for v in y['encoding']['variables']:
                                s = var_size_from_location(v['location'])
                                cs = bit_to_c_size(s)
                                vars.append(f'uint{cs}_t ' + v['name'])
                        imm_vars = ', '.join([str(i+1) for i in range(0,len(vars))])
                        name = y['name']
                        out.write('\n')
                        out.write(f'__attribute__((used))\n')
                        out.write(f'__attribute__((annotate ("immediate: {imm_vars}")))\n')
                        out.write(f'__attribute__((annotate ("helper-to-tcg")))\n')
                        out.write(f"void {re.sub(r'\.', r'_', name)}({', '.join(vars)}) {{\n")
                        op = y['operation()']
                        op = common.op_to_cpp(op)
                        #for size,bits in re.findall(r"([0-9]+)'b([0-9]+)", op):
                        #    size_rounded = 8*math.floor((Int(size)+8-1)/8)
                        #    print(f"(uint{size}_t) 0b{bits}")
                        out.write(op)
                        out.write('}\n')
                    except yaml.YAMLError as e:
                        print(e)
            out.write("};\n")
            out.write(postamble)

    if args.output_klee:
        for file in os.listdir(args.file):
            if not should_translate(file) and file not in manual_impls:
                continue
            klee_file = os.path.join(args.output_klee, os.path.splitext(file)[0]) + '.cpp'
            with open(os.path.join(args.file, file), 'r') as f:

                translated = ''
                with open(args.input_enabled, 'r') as in_enabled:
                    translated = in_enabled.read()

                y = None
                try:
                    y = yaml.safe_load(f)
                except yaml.YAMLError as e:
                    print(f'Error: {e}')
                    continue
                name = y['name']
                op_name = re.sub(r'\.', r'_', name)
                if len(translated) > 0 and not op_name in translated:
                    continue

                with open(klee_file, 'w') as out:
                    out.write('#include <klee/klee.h>')
                    out.write(str_includes)
                    out.write(str_reg_structs)
                    out.write(str_klee_operators)
                    out.write(f'#define INST_SIZE {int(len(y['encoding']['match'])/8)}')
                    out.write(str_memory_funcs_klee)
                    out.write(preamble)

                    vars = []
                    var_names = []
                    if 'variables' in y['encoding']:
                        for v in y['encoding']['variables']:
                            s = var_size_from_location(v['location'])
                            cs = bit_to_c_size(s)
                            vars.append(f'uint{cs}_t ' + v['name'])
                            var_names.append(v['name'])
                    out.write('\n')

                    if file in manual_impls:
                        out.write(manual_impls[file])
                    else:
                        out.write(f"void {re.sub(r'\.', r'_', name)}({', '.join(vars)}) {{\n")
                        op = y['operation()']
                        op = common.op_to_cpp(op)
                        out.write(op)
                        out.write('}\n')

                    out.write("};\n")

                    out.write('int main() {\n')
                    out.write('CPUArchState cpu;\n')
                    call_args = []
                    print_statements = []
                    result_print_statements = []
                    is_compressed = common.inst_is_compressed(y)
                    variables = common.variables(y)
                    print_info = {}
                    for i,v in enumerate(variables):
                        name = v['name']

                        is_imm = common.var_is_imm(y['operation()'], name)

                        var_size = var_size_from_location(v['location']) if is_imm else 32
                        cs = bit_to_c_size(var_size) if is_imm else 32
                        out.write(f'uint{cs}_t {name};\n')
                        if var_size < 32 or var_size > 32 and var_size < 64:
                            out.write(f'{name} &= (1ul << {var_size})-1;\n')

                        if is_imm:
                            out.write(f'klee_make_symbolic(&{name}, sizeof({name}), "{name}");\n')
                            if 'sign_extend' in v:
                                assert(v['sign_extend'] == True)
                                out.write(f"{name} = sextract{cs}({name}, 0, {s});\n")
                            if 'left_shift' in v:
                                out.write(f"{name} <<= {v['left_shift']};\n")
                            print_info[name] = ('imm', 0, False)
                            call_args.append(name);

                        elif not 'rd' in name:
                            out.write(f'klee_make_symbolic(&{name}, sizeof({name}), "{name}");\n')
                            compressed_offset = 8 if is_compressed else 0
                            offset = i+1+compressed_offset
                            print_info[name] = ('reg', offset, False)
                            out.write(f'cpu.X[{offset}] = {name};\n')
                            call_args.append(str(i+1));

                        else:
                            out.write(f'klee_make_symbolic(&{name}, sizeof({name}), "{name}");\n')
                            compressed_offset = 8 if is_compressed else 0
                            offset = i+1+compressed_offset
                            print_info[name] = ('reg', offset, True)
                            out.write(f'cpu.X[{offset}] = {name};\n')
                            call_args.append(str(i+1));

                        if 'not' in v:
                            not_values = v['not'] if isinstance(v['not'], list) else [v['not']]
                            for n in not_values:
                                out.write(f'klee_assume({name} != {n});\n')

                    for i,v in enumerate(variables):
                        name = v['name']
                        is_imm = common.var_is_imm(y['operation()'], name)
                        var_size = var_size_from_location(v['location']) if is_imm else 32
                        if var_size < 32 or var_size > 32 and var_size < 64:
                            out.write(f'{name} &= (1ul << {var_size})-1;\n')

                    out.write(f"cpu.{op_name}({', '.join(call_args)}")
                    out.write(');\n')

                    out.write(f'printf("- variables:\\n");\n')
                    for name  in print_info:
                        kind, offset, is_output = print_info[name]
                        out.write(f'printf("  - name: \\\"{name}\\\"\\n");\n')
                        if kind == 'reg':
                            out.write(f'printf("    in: %u\\n", {name});\n')
                        else:
                            out.write(f'printf("    in: %u\\n", {name});\n')

                        if is_output and kind == 'reg':
                            out.write(f'printf("    out: %u\\n", cpu.X[{offset}].value);\n')


                    out.write(f'printf("  overflow: %u\\n", overflow);\n')
                    out.write(f'printf("  underflow: %u\\n", underflow);\n')
                    out.write('if (has_jump) {\n')
                    out.write(f'    printf("  has_jump:\\n");\n')
                    out.write(f'    printf("  - valid_test_jump: %u\\n", has_valid_test_jump);\n')
                    out.write(f'    printf("  - jump_pc_offset: %u\\n", jump_pc_offset);\n')
                    out.write('}\n')
                    out.write(f"return 0;\n")
                    out.write('}\n')
                    out.flush()

                    command = ['clang-format', '-i', klee_file]
                    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    out, err = proc.communicate()
                    if proc.wait() != 0:
                        print(f"{' '.join(command)} exited with {proc.returncode}")
                        print(f"stdout:\n{out}")
                        print(f"stdout:\n{err}")

if __name__ == '__main__':
    main()
