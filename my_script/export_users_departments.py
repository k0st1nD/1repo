# coding: utf-8
"""
export_users_departments.py
---------------------------------------
Для каждого пользователя из data/jql_users_unique.csv ищет карточки
в проектах EMP и BUSEMP, где имя встречается в summary,
и извлекает значение поля customfield_22376 (Employee Department).

Результат: сводная таблица пользователей, сгруппированных по департаменту.
---------------------------------------
"""

import csv
import time
import configparser
from pathlib import Path
from atlassian import Jira
from collections import defaultdict, Counter

# === настройки ===
INPUT_FILE = Path("data/jql_users_unique.csv")
OUTPUT_FILE = Path("data/users_by_department.csv")
PROJECTS = ["EMP", "BUSEMP"]
DEPARTMENT_FIELD_KEY = "customfield_22376"
PAGE_LIMIT = 50
# =================


def read_config():
    cfg = configparser.ConfigParser()
    cfg.read("config.ini", encoding="utf-8")
    j = cfg["jira"]
    return j.get("host"), j.get("username"), j.get("password")


def connect_jira():
    host, username, password = read_config()
    print(f"[INFO] Connecting to Jira: {host}")
    return Jira(url=host, username=username, password=password, verify_ssl=False)


def read_usernames():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Файл не найден: {INPUT_FILE}")
    with INPUT_FILE.open("r", encoding="utf-8") as f:
        rdr = csv.DictReader(f, delimiter=";")
        return [row["Author"].strip() for row in rdr if row.get("Author")]


def search_user_cards(jira, username, dept_field_key):
    """
    Возвращает список значений департаментов для карточек,
    где summary содержит имя пользователя.
    """
    jql = f'project in ({",".join(PROJECTS)}) AND summary ~ "{username}"'
    results = []
    start = 0
    total = None
    while True:
        data = jira.jql(jql, fields=f"summary,{dept_field_key}", limit=PAGE_LIMIT, start=start)
        issues = data.get("issues", [])
        if not issues:
            break
        if total is None:
            total = data.get("total", len(issues))
        for issue in issues:
            fields = issue.get("fields", {})
            dept = fields.get(dept_field_key)

            # 🧩 обработка разных типов
            if isinstance(dept, dict):
                dept = dept.get("value") or dept.get("name")
            elif isinstance(dept, list):
                depts = []
                for d in dept:
                    if isinstance(d, dict):
                        depts.append(d.get("value") or d.get("name"))
                    elif isinstance(d, str):
                        depts.append(d)
                dept = ", ".join(filter(None, depts)) if depts else None
            elif not isinstance(dept, str):
                dept = str(dept) if dept else None

            if dept:
                results.append(dept)
        start += PAGE_LIMIT
        if start >= total:
            break
        time.sleep(0.2)
    return results



def main():
    jira = connect_jira()
    usernames = read_usernames()
    print(f"[INFO] Загружено {len(usernames)} пользователей из {INPUT_FILE}")

    user_to_dept = {}
    dept_to_users = defaultdict(set)

    for i, user in enumerate(usernames, 1):
        print(f"[{i}/{len(usernames)}] Поиск карточек для: {user} ...")
        depts = search_user_cards(jira, user, DEPARTMENT_FIELD_KEY)
        if not depts:
            print(f"    ❌ Нет карточек для {user}")
            continue

        # выбираем наиболее частый департамент
        most_common = Counter(depts).most_common(1)[0][0]
        user_to_dept[user] = most_common
        dept_to_users[most_common].add(user)
        print(f"    ✅ {user} → {most_common} ({len(depts)} карточек)")

    # сохраняем результат
    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Employee Department", "Users Count", "Users"])
        for dept, users in sorted(dept_to_users.items(), key=lambda x: x[0].lower()):
            w.writerow([dept, len(users), ", ".join(sorted(users))])

    print(f"\n✅ Готово. Результат сохранён в {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
