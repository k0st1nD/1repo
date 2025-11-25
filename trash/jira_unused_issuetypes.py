# coding: utf-8
"""
jira_unused_issuetypes.py
---------------------------------------
Находит типы задач (issuetype), которые не использовались
за последние 1.5 года (18 месяцев).

Логика:
1. Получаем все issuetype из Jira
2. Для каждого типа проверяем, есть ли задачи созданные за последние 18 месяцев
3. Выводим список неиспользуемых типов
---------------------------------------
"""

import configparser
from datetime import datetime, timezone, timedelta
from atlassian import Jira
from pathlib import Path
import csv
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# === настройки ===
MONTHS_AGO = 18  # проверяем за последние 18 месяцев (1.5 года)
OUTPUT_FILE = Path("data/unused_issuetypes.csv")
PAGE_LIMIT = 100  # для проверки достаточно небольшой выборки
# =================


def read_config():
    cfg = configparser.ConfigParser()
    config_path = Path(__file__).parent / "config.ini"
    cfg.read(config_path, encoding="utf-8")
    j = cfg["jira"]
    return j.get("host"), j.get("username"), j.get("password")


def connect_jira():
    host, username, password = read_config()
    print(f"[INFO] Connecting to Jira: {host}")
    return Jira(url=host, username=username, password=password, verify_ssl=False)


def get_all_issue_types(jira: Jira) -> list[dict]:
    """
    Получает все типы задач из Jira.
    Возвращает список словарей с id, name, description и т.д.
    """
    print("[INFO] Получаем все типы задач из Jira...")
    try:
        issue_types = jira.get_all_issue_types()
        print(f"[INFO] Найдено типов задач: {len(issue_types)}")
        return issue_types
    except Exception as e:
        print(f"[ERROR] Ошибка при получении типов задач: {e}")
        return []


def check_issuetype_usage(jira: Jira, issuetype_name: str, date_from: str) -> int:
    """
    Проверяет, есть ли задачи данного типа, созданные после date_from.
    Возвращает количество найденных задач.
    """
    jql = f'issuetype = "{issuetype_name}" AND created >= "{date_from}"'
    try:
        result = jira.jql(jql, fields="key", limit=1)
        total = result.get("total", 0)
        return total
    except Exception as e:
        print(f"   ⚠ Ошибка при проверке типа '{issuetype_name}': {e}")
        return -1  # -1 означает ошибку


def main():
    jira = connect_jira()

    # Вычисляем дату 18 месяцев назад
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=MONTHS_AGO * 30)
    date_str = cutoff_date.strftime("%Y-%m-%d")
    print(f"[INFO] Проверяем использование типов задач с {date_str}")

    # Получаем все типы задач
    issue_types = get_all_issue_types(jira)

    if not issue_types:
        print("[ERROR] Не удалось получить типы задач. Завершение.")
        return

    # Проверяем каждый тип
    unused_types = []
    used_types = []
    error_types = []

    print("\n[INFO] Проверяем использование каждого типа задач...")
    for idx, it in enumerate(issue_types, start=1):
        name = it.get("name", "Unknown")
        it_id = it.get("id", "N/A")
        description = it.get("description", "")

        print(f"[{idx}/{len(issue_types)}] Проверяем: {name} (ID: {it_id})")

        count = check_issuetype_usage(jira, name, date_str)

        if count == -1:
            # Ошибка при проверке
            error_types.append({
                "id": it_id,
                "name": name,
                "description": description,
                "count": "ERROR"
            })
        elif count == 0:
            # Не использовался
            print(f"   ✗ НЕ использовался (0 задач)")
            unused_types.append({
                "id": it_id,
                "name": name,
                "description": description,
                "count": count
            })
        else:
            # Использовался
            print(f"   ✓ Использовался ({count} задач)")
            used_types.append({
                "id": it_id,
                "name": name,
                "description": description,
                "count": count
            })

    # Сохраняем результаты
    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    with OUTPUT_FILE.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["ID", "Name", "Description", "Usage Status", "Issue Count"])

        # Сначала неиспользуемые
        for it in unused_types:
            w.writerow([
                it["id"],
                it["name"],
                it["description"],
                "UNUSED",
                it["count"]
            ])

        # Затем используемые
        for it in used_types:
            w.writerow([
                it["id"],
                it["name"],
                it["description"],
                "USED",
                it["count"]
            ])

        # И ошибки
        for it in error_types:
            w.writerow([
                it["id"],
                it["name"],
                it["description"],
                "ERROR",
                it["count"]
            ])

    # Выводим итоговую статистику
    print("\n" + "="*60)
    print("РЕЗУЛЬТАТЫ:")
    print("="*60)
    print(f"Всего типов задач: {len(issue_types)}")
    print(f"Используемых (за последние {MONTHS_AGO} мес.): {len(used_types)}")
    print(f"НЕ используемых: {len(unused_types)}")
    print(f"Ошибок при проверке: {len(error_types)}")

    if unused_types:
        print("\nНеиспользуемые типы задач:")
        for it in unused_types:
            print(f"  - {it['name']} (ID: {it['id']})")

    print(f"\n✅ Готово. Детальный отчёт сохранён в {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
