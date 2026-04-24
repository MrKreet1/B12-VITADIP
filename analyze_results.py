#!/usr/bin/env python3
"""
Разбор результатов ORCA-оптимизаций B12.

Что делает:
  1. Проходит все поддиректории в jobs_dir.
  2. Парсит .out: проверяет нормальное завершение, забирает FINAL SINGLE
     POINT ENERGY после последнего цикла оптимизации.
  3. Извлекает оптимизированные координаты из <name>.xyz (ORCA пишет его
     автоматически в конце успешной оптимизации).
  4. Сохраняет таблицу энергий и объединённый XYZ-файл всех оптимизированных
     структур, отсортированный по энергии (от минимума).
  5. Выводит топ-N и минимальную структуру отдельным файлом.
"""

import argparse
import csv
import glob
import os
import re

HARTREE_TO_EV  = 27.211386245988
HARTREE_TO_KCAL = 627.5094740631

def parse_energy(out_path):
    """Возвращает последнюю FINAL SINGLE POINT ENERGY (или None)."""
    try:
        with open(out_path, errors="ignore") as f:
            text = f.read()
    except OSError:
        return None
    matches = re.findall(r"FINAL SINGLE POINT ENERGY\s+(-?\d+\.\d+)", text)
    if not matches:
        return None
    return float(matches[-1])

def terminated_normally(out_path):
    try:
        with open(out_path, errors="ignore") as f:
            return "ORCA TERMINATED NORMALLY" in f.read()
    except OSError:
        return False

def opt_converged(out_path):
    try:
        with open(out_path, errors="ignore") as f:
            txt = f.read()
    except OSError:
        return False
    return "HURRAY" in txt or "THE OPTIMIZATION HAS CONVERGED" in txt

def read_xyz(path):
    with open(path) as f:
        lines = f.readlines()
    n = int(lines[0].strip())
    comment = lines[1].rstrip("\n")
    atoms = [l.rstrip("\n") for l in lines[2:2 + n]]
    return n, comment, atoms

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--jobs-dir", default="jobs")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--out-csv", default="results.csv")
    p.add_argument("--out-combined", default="all_optimized.xyz")
    p.add_argument("--out-best", default="best_structure.xyz")
    args = p.parse_args()

    job_dirs = sorted([d for d in glob.glob(os.path.join(args.jobs_dir, "*"))
                       if os.path.isdir(d)])
    if not job_dirs:
        raise SystemExit(f"Нет заданий в {args.jobs_dir}")

    rows = []
    for d in job_dirs:
        name = os.path.basename(d)
        out  = os.path.join(d, name + ".out")
        xyz  = os.path.join(d, name + ".xyz")  # оптимизированная геометрия

        if not os.path.isfile(out):
            rows.append(dict(name=name, status="NO_OUT", energy=None,
                             converged=False, xyz=None))
            continue

        ended  = terminated_normally(out)
        conv   = opt_converged(out)
        energy = parse_energy(out)
        has_xyz = os.path.isfile(xyz)

        if ended and conv and energy is not None and has_xyz:
            status = "OK"
        elif ended and energy is not None and has_xyz:
            status = "NOT_CONVERGED"
        elif ended:
            status = "NO_ENERGY"
        else:
            status = "CRASHED"

        rows.append(dict(name=name, status=status, energy=energy,
                         converged=conv, xyz=xyz if has_xyz else None))

    # Сортировка: сначала валидные OK-структуры по возрастанию энергии
    valid = [r for r in rows if r["status"] == "OK"]
    valid.sort(key=lambda r: r["energy"])
    others = [r for r in rows if r["status"] != "OK"]

    if not valid:
        print("ВНИМАНИЕ: нет ни одного успешно сошедшегося расчёта.")
    else:
        e_min = valid[0]["energy"]
        for r in valid:
            r["dE_eV"]   = (r["energy"] - e_min) * HARTREE_TO_EV
            r["dE_kcal"] = (r["energy"] - e_min) * HARTREE_TO_KCAL

    # CSV
    with open(args.out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "name", "status", "E_hartree",
                    "dE_eV", "dE_kcal_mol", "converged"])
        for i, r in enumerate(valid, start=1):
            w.writerow([i, r["name"], r["status"],
                        f"{r['energy']:.8f}",
                        f"{r['dE_eV']:.4f}",
                        f"{r['dE_kcal']:.3f}",
                        r["converged"]])
        for r in others:
            w.writerow(["-", r["name"], r["status"],
                        "" if r["energy"] is None else f"{r['energy']:.8f}",
                        "", "", r["converged"]])

    # Объединённый XYZ всех валидных, отсортированный по энергии
    with open(args.out_combined, "w") as fout:
        for i, r in enumerate(valid, start=1):
            n, _, atoms = read_xyz(r["xyz"])
            fout.write(f"{n}\n")
            fout.write(f"rank={i}  E={r['energy']:.8f} Eh  "
                       f"dE={r['dE_eV']:.4f} eV  name={r['name']}\n")
            for a in atoms:
                fout.write(a + ("\n" if not a.endswith("\n") else ""))

    # Файл с лучшей структурой
    if valid:
        best = valid[0]
        n, _, atoms = read_xyz(best["xyz"])
        with open(args.out_best, "w") as f:
            f.write(f"{n}\n")
            f.write(f"B12 global minimum candidate: {best['name']}  "
                    f"E={best['energy']:.8f} Eh\n")
            for a in atoms:
                f.write(a + ("\n" if not a.endswith("\n") else ""))

    # Вывод на экран
    print("\n=== СТАТИСТИКА ===")
    stat_counts = {}
    for r in rows:
        stat_counts[r["status"]] = stat_counts.get(r["status"], 0) + 1
    for k, v in stat_counts.items():
        print(f"  {k:15s} {v}")

    print(f"\n=== ТОП-{args.top} по энергии ===")
    hdr = f"{'#':>3}  {'name':40s}  {'E (Ha)':>14s}  {'dE (eV)':>10s}  {'dE (kcal/mol)':>14s}"
    print(hdr)
    print("-" * len(hdr))
    for i, r in enumerate(valid[:args.top], start=1):
        print(f"{i:>3}  {r['name']:40s}  {r['energy']:>14.8f}  "
              f"{r['dE_eV']:>10.4f}  {r['dE_kcal']:>14.3f}")

    if valid:
        print(f"\nЛучшая структура: {valid[0]['name']}")
        print(f"  Энергия:   {valid[0]['energy']:.8f} Hartree")
        print(f"  Сохранена: {args.out_best}")
    print(f"\nТаблица:             {args.out_csv}")
    print(f"Все структуры XYZ:  {args.out_combined}")

if __name__ == "__main__":
    main()
