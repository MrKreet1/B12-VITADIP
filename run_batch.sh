#!/usr/bin/env bash
#
# Последовательный запуск всех ORCA-задач.
# Использование:
#   ./run_batch.sh [jobs_dir]
# По умолчанию jobs_dir=jobs.
#
# Перед запуском убедитесь, что ORCA в PATH:
#   which orca
# и что используется полный путь (ORCA требует полный путь для параллельного режима).

set -u

JOBS_DIR="${1:-jobs}"

# Находим полный путь к orca (требуется для nprocs > 1)
ORCA_BIN="$(command -v orca)"
if [[ -z "${ORCA_BIN}" ]]; then
    echo "ERROR: orca не найдена в PATH" >&2
    exit 1
fi
echo "Использую ORCA: ${ORCA_BIN}"

# Лог прогресса
PROGRESS_LOG="${JOBS_DIR}/_progress.log"
: > "${PROGRESS_LOG}"

# Считаем задачи
mapfile -t JOB_DIRS < <(find "${JOBS_DIR}" -mindepth 1 -maxdepth 1 -type d | sort)
TOTAL=${#JOB_DIRS[@]}
echo "Найдено заданий: ${TOTAL}"

i=0
for d in "${JOB_DIRS[@]}"; do
    i=$((i+1))
    name="$(basename "$d")"
    inp="${d}/${name}.inp"
    out="${d}/${name}.out"

    if [[ ! -f "${inp}" ]]; then
        echo "[${i}/${TOTAL}] SKIP ${name} (нет .inp)"
        continue
    fi

    # Пропускаем успешно завершённые
    if [[ -f "${out}" ]] && grep -q "ORCA TERMINATED NORMALLY" "${out}" 2>/dev/null; then
        echo "[${i}/${TOTAL}] DONE уже есть: ${name}"
        echo "${name} SKIPPED_ALREADY_DONE" >> "${PROGRESS_LOG}"
        continue
    fi

    echo "[${i}/${TOTAL}] RUN  ${name}"
    START=$(date +%s)
    (
        cd "${d}" && "${ORCA_BIN}" "${name}.inp" > "${name}.out" 2> "${name}.err"
    )
    RC=$?
    END=$(date +%s)
    DUR=$((END - START))

    if [[ ${RC} -eq 0 ]] && grep -q "ORCA TERMINATED NORMALLY" "${out}" 2>/dev/null; then
        echo "[${i}/${TOTAL}] OK   ${name} (${DUR}s)"
        echo "${name} OK ${DUR}" >> "${PROGRESS_LOG}"
    else
        echo "[${i}/${TOTAL}] FAIL ${name} (rc=${RC}, ${DUR}s)"
        echo "${name} FAIL rc=${RC} ${DUR}" >> "${PROGRESS_LOG}"
    fi
done

echo "Готово. Лог: ${PROGRESS_LOG}"
