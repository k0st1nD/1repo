# coding: utf-8
"""
analyze_department_operations.py
---------------------------------------
Анализирует, какие операции чаще всего выполняют сотрудники
разных Employee Department, на основе:
- data/jql_users_activity.csv
- data/users_by_department.csv

Результат:
1. Полная таблица операций по департаментам (operations_by_department.csv)
2. Сводная таблица с топ-3 операций на департамент, отсортированная по убыванию активности
   (department_top3_operations.csv)
---------------------------------------
"""

import pandas as pd
from pathlib import Path

# === настройки ===
ACTIVITY_FILE = Path("data/jql_users_activity.csv")
DEPTS_FILE = Path("data/users_by_department.csv")
OUTPUT_TABLE_FULL = Path("data/operations_by_department.csv")
OUTPUT_TABLE_TOP3 = Path("data/department_top3_operations.csv")
# =================


def main():
    if not ACTIVITY_FILE.exists() or not DEPTS_FILE.exists():
        raise FileNotFoundError("Отсутствуют входные файлы jql_users_activity.csv или users_by_department.csv")

    print(f"[INFO] Загружаем данные...")
    df_acts = pd.read_csv(ACTIVITY_FILE, sep=";", encoding="utf-8")
    df_depts = pd.read_csv(DEPTS_FILE, sep=";", encoding="utf-8")

    df_acts.columns = [c.strip() for c in df_acts.columns]
    df_depts.columns = [c.strip() for c in df_depts.columns]

    # соответствие user → department
    dept_map = {}
    for _, row in df_depts.iterrows():
        dept = row["Employee Department"]
        users = [u.strip() for u in str(row["Users"]).split(",")]
        for u in users:
            dept_map[u] = dept

    print(f"[INFO] Найдено {len(dept_map)} пользователей с департаментами")

    # добавляем колонку департамента
    df_acts["Employee Department"] = df_acts["Author"].map(dept_map)
    df_acts = df_acts.dropna(subset=["Employee Department"])

    if "Field" not in df_acts.columns:
        raise KeyError("В файле активности нет колонки 'Field' — нужно уточнить, где указаны типы изменений.")

    # полная таблица
    pivot = (
        df_acts.groupby(["Employee Department", "Field"])
        .size()
        .reset_index(name="Count")
        .sort_values(["Employee Department", "Count"], ascending=[True, False])
    )

    pivot.to_csv(OUTPUT_TABLE_FULL, sep=";", index=False, encoding="utf-8-sig")
    print(f"[INFO] Полная таблица сохранена в {OUTPUT_TABLE_FULL}")

    # считаем общее количество действий на департамент
    total_by_dept = pivot.groupby("Employee Department")["Count"].sum().to_dict()

    # топ-3 операций по каждому департаменту
    top3_rows = []
    for dept, group in pivot.groupby("Employee Department"):
        top_ops = group.nlargest(3, "Count")
        ops_summary = ", ".join([f"{row.Field} ({row.Count})" for _, row in top_ops.iterrows()])
        top3_rows.append({
            "Employee Department": dept,
            "Total Actions": total_by_dept.get(dept, 0),
            "Top 3 Operations": ops_summary
        })

    df_top3 = pd.DataFrame(top3_rows)
    df_top3 = df_top3.sort_values("Total Actions", ascending=False)

    df_top3.to_csv(OUTPUT_TABLE_TOP3, sep=";", index=False, encoding="utf-8-sig")

    print(f"[INFO] Сводная таблица (ТОП-3) сохранена в {OUTPUT_TABLE_TOP3}")
    print("\n=== Топ-10 департаментов по активности ===")
    print(df_top3.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
