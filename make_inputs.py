#!/usr/bin/env python3
"""
Формирует ORCA input-файлы из всех XYZ в ./configs/.

Настройки метода подобраны для первичного скрининга на 8 ядрах / 24 ГБ:
  - BP86 + def2-SVP + RI-J (def2/J) — быстро и надёжно для GGA.
  - TightSCF, Opt, D3BJ-дисперсия.
  - Мультиплетность по умолчанию 1 (синглет). Для триплета см. --mult 3.

Для уточнения топ-кандидатов после скрининга используйте метод уровня
B3LYP/def2-TZVP D3BJ — пересчитайте только лучшие структуры.
"""

import argparse
import os
import glob

INPUT_TEMPLATE = """! {method} {basis} {aux} {ri} Opt TightSCF D3BJ
! SlowConv

%pal nprocs {nprocs} end
%maxcore {maxcore}

%geom
  MaxIter 300
end

* xyz {charge} {mult}
{xyz_block}*
"""

def read_xyz_body(path):
    """Возвращает строки с атомами из XYZ-файла (без заголовка и комментария)."""
    with open(path) as f:
        lines = f.readlines()
    n = int(lines[0].strip())
    body = lines[2:2 + n]
    return "".join(body)

def build_input(xyz_path, out_dir, *, method, basis, aux, ri,
                charge, mult, nprocs, maxcore):
    base = os.path.splitext(os.path.basename(xyz_path))[0]
    job_dir = os.path.join(out_dir, base)
    os.makedirs(job_dir, exist_ok=True)
    xyz_body = read_xyz_body(xyz_path)
    content = INPUT_TEMPLATE.format(
        method=method, basis=basis, aux=aux, ri=ri,
        nprocs=nprocs, maxcore=maxcore,
        charge=charge, mult=mult, xyz_block=xyz_body,
    )
    inp_path = os.path.join(job_dir, base + ".inp")
    with open(inp_path, "w") as f:
        f.write(content)
    return inp_path

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--configs-dir", default="configs")
    p.add_argument("--jobs-dir", default="jobs")
    p.add_argument("--method", default="BP86",
                   help="Функционал (BP86 для скрининга, B3LYP для уточнения)")
    p.add_argument("--basis", default="def2-SVP",
                   help="Базис (def2-SVP быстро, def2-TZVP точнее)")
    p.add_argument("--aux", default="def2/J",
                   help="Вспомогательный базис для RI")
    p.add_argument("--ri", default="RI",
                   help="RI-ключ: 'RI' для GGA, 'RIJCOSX' для гибридов")
    p.add_argument("--charge", type=int, default=0)
    p.add_argument("--mult", type=int, default=1,
                   help="Спиновая мультиплетность (1=синглет, 3=триплет)")
    p.add_argument("--nprocs", type=int, default=8)
    p.add_argument("--maxcore", type=int, default=2500,
                   help="МБ на ядро (8*2500=20000 МБ, оставит запас)")
    p.add_argument("--suffix", default="",
                   help="Суффикс для имени поддиректории (напр. '_triplet')")
    args = p.parse_args()

    xyz_files = sorted(glob.glob(os.path.join(args.configs_dir, "*.xyz")))
    if not xyz_files:
        raise SystemExit(f"Не найдено XYZ в {args.configs_dir}")

    jobs_dir = args.jobs_dir + args.suffix
    os.makedirs(jobs_dir, exist_ok=True)

    created = []
    for xyz in xyz_files:
        inp = build_input(
            xyz, jobs_dir,
            method=args.method, basis=args.basis, aux=args.aux, ri=args.ri,
            charge=args.charge, mult=args.mult,
            nprocs=args.nprocs, maxcore=args.maxcore,
        )
        created.append(inp)

    print(f"Создано ORCA-input файлов: {len(created)}")
    print(f"Каталог заданий: {jobs_dir}/<name>/<name>.inp")

if __name__ == "__main__":
    main()
