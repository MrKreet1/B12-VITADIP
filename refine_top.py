#!/usr/bin/env python3
"""
Готовит re-optimization топ-N структур со скрининга на более точном
уровне теории (по умолчанию B3LYP/def2-TZVP D3BJ + RIJCOSX).

Берёт все OK-результаты из ./jobs/, сортирует по энергии,
и для топ-N создаёт новые ORCA-входы в ./jobs_refined/,
используя оптимизированные геометрии со скрининга как стартовые.
"""

import argparse
import csv
import glob
import os
import re
import shutil

TEMPLATE = """! {method} {basis} {aux} {ri} Opt TightSCF D3BJ Freq

%pal nprocs {nprocs} end
%maxcore {maxcore}

%geom
  MaxIter 500
end

* xyz {charge} {mult}
{xyz_block}*
"""

def parse_energy(out_path):
    try:
        with open(out_path, errors="ignore") as f:
            txt = f.read()
    except OSError:
        return None
    m = re.findall(r"FINAL SINGLE POINT ENERGY\s+(-?\d+\.\d+)", txt)
    return float(m[-1]) if m else None

def terminated_ok(out_path):
    try:
        with open(out_path, errors="ignore") as f:
            return "ORCA TERMINATED NORMALLY" in f.read()
    except OSError:
        return False

def read_xyz_body(path):
    with open(path) as f:
        lines = f.readlines()
    n = int(lines[0].strip())
    return "".join(lines[2:2 + n])

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--jobs-dir", default="jobs")
    p.add_argument("--refined-dir", default="jobs_refined")
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--method", default="B3LYP")
    p.add_argument("--basis", default="def2-TZVP")
    p.add_argument("--aux", default="def2/J")
    p.add_argument("--ri", default="RIJCOSX")
    p.add_argument("--charge", type=int, default=0)
    p.add_argument("--mult", type=int, default=1)
    p.add_argument("--nprocs", type=int, default=8)
    p.add_argument("--maxcore", type=int, default=2500)
    args = p.parse_args()

    job_dirs = sorted([d for d in glob.glob(os.path.join(args.jobs_dir, "*"))
                       if os.path.isdir(d)])

    records = []
    for d in job_dirs:
        name = os.path.basename(d)
        out  = os.path.join(d, name + ".out")
        xyz  = os.path.join(d, name + ".xyz")
        if not (os.path.isfile(out) and os.path.isfile(xyz)): continue
        if not terminated_ok(out): continue
        e = parse_energy(out)
        if e is None: continue
        records.append((e, name, xyz))

    records.sort(key=lambda r: r[0])
    top = records[:args.top]
    print(f"Отобрано {len(top)} структур из {len(records)} успешных.")

    os.makedirs(args.refined_dir, exist_ok=True)
    for rank, (e, name, xyz) in enumerate(top, start=1):
        new_name = f"rank{rank:02d}_{name}"
        dst_dir = os.path.join(args.refined_dir, new_name)
        os.makedirs(dst_dir, exist_ok=True)
        body = read_xyz_body(xyz)
        inp  = TEMPLATE.format(
            method=args.method, basis=args.basis, aux=args.aux, ri=args.ri,
            nprocs=args.nprocs, maxcore=args.maxcore,
            charge=args.charge, mult=args.mult, xyz_block=body,
        )
        with open(os.path.join(dst_dir, new_name + ".inp"), "w") as f:
            f.write(inp)
        print(f"  [{rank:2d}] E={e:.6f} -> {dst_dir}/{new_name}.inp")

    print(f"\nДля запуска: ./run_batch.sh {args.refined_dir}")

if __name__ == "__main__":
    main()
