# coding: utf-8
"""
jira_status_durations_pivot.py
---------------------------------------
Преобразует файл status_durations_CAMPEIGN.csv
в таблицу формата:
IssueKey | Created | time_in_Created | time_in_InProgress | ... | ResolutionDate | T2M (days)
---------------------------------------
"""

import pandas as pd
from pathlib import Path

# === настройки ===
INPUT_FILE = Path("data/status_durations_CAMPEIGN.csv")
OUTPUT_FILE = Path("data/status_durations_pivot.csv")
# =================


def main():
    print(f"[INFO] Загружаем {INPUT_FILE}")
    df = pd.read_csv(INPUT_FILE, sep=";", encoding="utf-8-sig")

    # чистим названия статусов
    df["Status"] = df["Status"].astype(str).str.strip()

    # оставляем только нужные поля
    df = df[["Issue Key", "Status", "Duration (days)", "Entered", "Left"]]

    # сводная таблица: issuekey → столбцы со временем в статусах
    pivot = df.pivot_table(
        index="Issue Key",
        columns="Status",
        values="Duration (days)",
        aggfunc="sum",
        fill_value=0
    ).reset_index()

    # читаем даты created / resolution из исходных данных (первые и последние записи)
    created_dates = (
        df.groupby("Issue Key")["Entered"].min().rename("Created Date")
    )
    resolution_dates = (
        df.groupby("Issue Key")["Left"].max().rename("Resolution Date")
    )

    result = pivot.merge(created_dates, on="Issue Key", how="left")
    result = result.merge(resolution_dates, on="Issue Key", how="left")

    # вычисляем T2M = ResolutionDate - CreatedDate
    result["Created Date"] = pd.to_datetime(result["Created Date"], errors="coerce")
    result["Resolution Date"] = pd.to_datetime(result["Resolution Date"], errors="coerce")
    result["T2M (days)"] = (result["Resolution Date"] - result["Created Date"]).dt.total_seconds() / 86400

    # сортировка столбцов: issuekey → даты → статусы → T2M
    static_cols = ["Issue Key", "Created Date"]
    status_cols = [c for c in result.columns if c not in ["Issue Key", "Created Date", "Resolution Date", "T2M (days)"]]
    result = result[["Issue Key", "Created Date", *status_cols, "Resolution Date", "T2M (days)"]]

    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    result.to_csv(OUTPUT_FILE, sep=";", encoding="utf-8-sig", index=False)
    print(f"[INFO] Готово → {OUTPUT_FILE}")
    print(f"[INFO] Всего строк: {len(result)}")


if __name__ == "__main__":
    main()
