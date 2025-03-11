#!/usr/bin/env python3

import common
import argparse
import os

def main():
    parser = argparse.ArgumentParser(
        prog='csr',
        description=''
    )
    parser.add_argument('--inst-dir', required=True)
    parser.add_argument('--csr-dir', required=True)
    parser.add_argument('--out-c', required=True)
    parser.add_argument('--out-h', required=True)
    args = parser.parse_args()

    # Print instructions which touch CSR
    for file in os.listdir(args.inst_dir):
        y = common.load_yaml_or_exit(os.path.join(args.inst_dir, file))
        if 'CSR' in y['operation()']:
            print(f"{y['name']}")
            #print(y['operation()'])

    csrs = {}
    for file in os.listdir(args.csr_dir):
        if not file.endswith('.yaml'):
            continue
        y = common.load_yaml_or_exit(os.path.join(args.csr_dir, file))
        csrs[y['name']] = y

    for csr in csrs:
        print(csr)

    with open(args.out_c, 'w') as out:
        out.write('#include "qemu/osdep.h"\n')
        out.write('#include "cpu.h"\n')
        out.write('#include "cpu_vendorid.h"\n')
        out.write('#include "xqciu_csr.h"\n')
        out.write('\n')

        out.write('static RISCVException any(CPURISCVState *env, int csrno)\n')
        out.write('{\n')
        out.write('    return RISCV_EXCP_NONE;\n')
        out.write('}\n')
        out.write('\n')

        for csr in csrs:
            out.write(f"static RISCVException read_{csr}(CPURISCVState *env, int csrno, target_ulong *val)\n")
            out.write("{\n")
            out.write(f"    *val = env->{csr};\n")
            out.write("    return RISCV_EXCP_NONE;\n")
            out.write("}\n")

            out.write(f"static RISCVException write_{csr}(CPURISCVState *env, int csrno, target_ulong val)\n")
            out.write("{\n")
            out.write(f"    env->{csr} = val;\n")
            out.write("    return RISCV_EXCP_NONE;\n")
            out.write("}\n")

        out.write('void qc_iu_register_custom_csrs(RISCVCPU *cpu)\n')
        out.write('{\n')
        for csr in csrs:
            out.write(f"    riscv_set_csr_ops(CSR_{csr.upper()}, &(riscv_csr_operations){{\"{csr}\", any, read_{csr}, write_{csr}}});\n")
        out.write('}\n')

    with open(args.out_h, 'w') as out:
        out.write('\n')
        for csr in csrs:
            out.write(f"#define CSR_{csr.upper()} {hex(csrs[csr]['address'])}\n")

        # TODO handling of rv32 rv64 not correct
        for csr in csrs:
            for field in csrs[csr]['fields']:
                mask = 0
                if 'location' in csrs[csr]['fields'][field]:
                    loc_str = csrs[csr]['fields'][field]['location']
                    for start,len in common.ranges_in_location(str(loc_str)):
                        mask |= ((1 << len) - 1) << start
                    out.write(f"#define {csr.upper()}_{field} {hex(mask)}\n")
                elif 'location_rv32' in csrs[csr]['fields'][field]:
                    loc_str = csrs[csr]['fields'][field]['location_rv32']
                    for start,len in common.ranges_in_location(str(loc_str)):
                        mask |= ((1 << len) - 1) << start
                    out.write(f"#define {csr.upper()}_{field} {hex(mask)}\n")
                elif 'location_rv64' in csrs[csr]['fields'][field]:
                    loc_str = csrs[csr]['fields'][field]['location_rv64']
                    for start,len in common.ranges_in_location(str(loc_str)):
                        mask |= ((1 << len) - 1) << start
                    out.write(f"#define {csr.upper()}_{field} {hex(mask)}\n")

        out.write('void qc_iu_register_custom_csrs(RISCVCPU *cpu);\n')

if __name__ == '__main__':
    main()
