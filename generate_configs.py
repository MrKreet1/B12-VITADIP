#!/usr/bin/env python3
"""
Генерация стартовых конфигураций кластера B12.

Создаёт набор XYZ-файлов с разной топологией и разным масштабом
межатомных расстояний. Масштабирование делается так, чтобы
минимальное попарное расстояние равнялось заданному значению
(параметр `target_nn` в ангстремах).
"""

import os
import numpy as np
from itertools import product, permutations

OUT_DIR = "configs"

# ---------------------------------------------------------------------------
# Топологии (12 точек каждая). Возвращают сырые координаты,
# масштабируются позже функцией `normalize_nn`.
# ---------------------------------------------------------------------------

def icosahedron():
    """Регулярный икосаэдр — 12 вершин."""
    phi = (1 + np.sqrt(5)) / 2
    pts = []
    for s1, s2 in product([-1, 1], repeat=2):
        pts.append([0, s1, s2 * phi])
        pts.append([s1, s2 * phi, 0])
        pts.append([s2 * phi, 0, s1])
    return np.array(pts, dtype=float)

def cuboctahedron():
    """Кубооктаэдр — 12 вершин."""
    pts = []
    for s1, s2 in product([-1, 1], repeat=2):
        pts.append([0, s1, s2])
        pts.append([s1, 0, s2])
        pts.append([s1, s2, 0])
    return np.array(pts, dtype=float)

def hex_antiprism(height_ratio=0.8):
    """Гексагональная антипризма: два шестиугольника со сдвигом."""
    pts = []
    for i in range(6):
        a = 2 * np.pi * i / 6
        pts.append([np.cos(a), np.sin(a),  height_ratio / 2])
    for i in range(6):
        a = 2 * np.pi * (i + 0.5) / 6
        pts.append([np.cos(a), np.sin(a), -height_ratio / 2])
    return np.array(pts, dtype=float)

def hex_prism(height_ratio=0.8):
    """Гексагональная призма: два шестиугольника без сдвига."""
    pts = []
    for i in range(6):
        a = 2 * np.pi * i / 6
        pts.append([np.cos(a), np.sin(a),  height_ratio / 2])
        pts.append([np.cos(a), np.sin(a), -height_ratio / 2])
    return np.array(pts, dtype=float)

def truncated_tetrahedron():
    """Усечённый тетраэдр — 12 вершин."""
    base = [(0, 1, 3), (0, 3, 1), (1, 0, 3), (3, 0, 1), (1, 3, 0), (3, 1, 0)]
    pts = set()
    sign_sets = [(1, 1, 1), (-1, -1, 1), (-1, 1, -1), (1, -1, -1)]
    for b in base:
        for s in sign_sets:
            pts.add((s[0] * b[0], s[1] * b[1], s[2] * b[2]))
    pts = np.array(sorted(pts), dtype=float)
    return pts[:12]

def quasi_planar_convex():
    """Квазипланарная выпуклая «чаша» — для B12 это наиболее обсуждаемый мотив."""
    pts = []
    # 3 внутренних атома (треугольник)
    for i in range(3):
        a = 2 * np.pi * i / 3
        pts.append([0.55 * np.cos(a), 0.55 * np.sin(a), 0.15])
    # 9 внешних атомов
    for i in range(9):
        a = 2 * np.pi * i / 9 + 0.1
        pts.append([1.75 * np.cos(a), 1.75 * np.sin(a), -0.05])
    return np.array(pts, dtype=float)

def double_ring():
    """Две связанные гексагональные «шестёрки» в одной плоскости."""
    pts = []
    for cx in (-1.4, 1.4):
        for i in range(6):
            a = 2 * np.pi * i / 6
            pts.append([cx + np.cos(a), np.sin(a), 0.0])
    return np.array(pts, dtype=float)

def random_blob(seed, min_sep=0.55):
    """Случайное облако внутри шара с ограничением минимального расстояния."""
    rng = np.random.default_rng(seed)
    pts = []
    tries = 0
    while len(pts) < 12 and tries < 10000:
        p = rng.uniform(-1, 1, 3)
        if np.linalg.norm(p) > 1:
            tries += 1
            continue
        if all(np.linalg.norm(p - q) >= min_sep for q in pts):
            pts.append(p)
        tries += 1
    if len(pts) < 12:
        raise RuntimeError("random_blob: не удалось расставить 12 атомов")
    return np.array(pts, dtype=float)

def perturb(coords, sigma, seed):
    """Случайное шевеление координат (в долях нормированного расстояния)."""
    rng = np.random.default_rng(seed)
    return coords + rng.normal(0.0, sigma, coords.shape)

# ---------------------------------------------------------------------------
# Нормировка и запись
# ---------------------------------------------------------------------------

def min_pairwise(coords):
    d = np.inf
    n = len(coords)
    for i in range(n):
        for j in range(i + 1, n):
            v = np.linalg.norm(coords[i] - coords[j])
            if v < d:
                d = v
    return d

def normalize_nn(coords, target_nn):
    """Масштабирует координаты так, чтобы min попарное расстояние = target_nn (Å)."""
    d = min_pairwise(coords)
    return coords * (target_nn / d)

def center(coords):
    return coords - coords.mean(axis=0)

def write_xyz(coords, path, comment=""):
    with open(path, "w") as f:
        f.write(f"12\n{comment}\n")
        for c in coords:
            f.write(f"B  {c[0]:14.8f}  {c[1]:14.8f}  {c[2]:14.8f}\n")

# ---------------------------------------------------------------------------
# Главная процедура
# ---------------------------------------------------------------------------

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # Набор масштабов — ближайшее межатомное расстояние в Å.
    # 1.6 — около равновесного, 5.0 — заведомо «разорванный» (по запросу пользователя).
    nn_scales = [1.6, 1.8, 2.0, 2.5, 3.0, 5.0]

    # Базовые топологии
    topologies = {
        "icosahedron":      icosahedron(),
        "cuboctahedron":    cuboctahedron(),
        "hex_antiprism":    hex_antiprism(),
        "hex_prism":        hex_prism(),
        "trunc_tetrahedron":truncated_tetrahedron(),
        "quasi_planar":     quasi_planar_convex(),
        "double_ring":      double_ring(),
    }

    records = []

    # 1) Регулярные топологии × масштабы
    for name, raw in topologies.items():
        raw = center(raw)
        for nn in nn_scales:
            coords = normalize_nn(raw, nn)
            tag = f"{name}_nn{nn:.2f}"
            fn = os.path.join(OUT_DIR, tag + ".xyz")
            write_xyz(coords, fn, comment=f"{name}, nn={nn:.2f} A")
            records.append(tag)

    # 2) Возмущённые копии нескольких топологий — расширяем выборку
    perturb_sources = ["icosahedron", "quasi_planar", "hex_antiprism", "cuboctahedron"]
    for name in perturb_sources:
        raw = center(topologies[name])
        for nn in [1.7, 2.0]:
            base = normalize_nn(raw, nn)
            for seed in range(3):
                coords = perturb(base, sigma=0.15, seed=seed)
                tag = f"{name}_nn{nn:.2f}_perturb{seed}"
                fn = os.path.join(OUT_DIR, tag + ".xyz")
                write_xyz(coords, fn, comment=f"{name} perturbed s={seed}")
                records.append(tag)

    # 3) Случайные конфигурации
    for seed in range(6):
        raw = random_blob(seed)
        for nn in [1.7, 2.0]:
            coords = normalize_nn(center(raw), nn)
            tag = f"random{seed}_nn{nn:.2f}"
            fn = os.path.join(OUT_DIR, tag + ".xyz")
            write_xyz(coords, fn, comment=f"random seed={seed}")
            records.append(tag)

    # Индекс
    with open(os.path.join(OUT_DIR, "INDEX.txt"), "w") as f:
        f.write("\n".join(records) + "\n")

    print(f"Сгенерировано конфигураций: {len(records)}")
    print(f"Файлы: ./{OUT_DIR}/*.xyz")
    print(f"Индекс: ./{OUT_DIR}/INDEX.txt")

if __name__ == "__main__":
    main()
