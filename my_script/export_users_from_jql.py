# coding: utf-8
"""
export_users_from_jql.py
Выгружает из Jira список всех пользователей, которые что-либо меняли
в задачах, отобранных JQL-запросом. Пишет подробную активность и уникальный список пользователей.

Зависимости:
    pip install atlassian-python-api python-dateutil simplejson tqdm

Примеры:
    python export_users_from_jql.py --jql "project = CLM AND updated >= -30d"
    python export_users_from_jql.py --jql-file my_query.jql --limit 200 --outfile data/my_activity.csv
"""

import csv
import sys
import json
import argparse
import configparser
from pathlib import Path
from math import ceil
from datetime import datetime
from dateutil.parser import parse as dtparse
from tqdm import tqdm

try:
    from atlassian import Jira
except ImportError:
    print("Не найден пакет atlassian-python-api. Установи: pip install atlassian-python-api")
    sys.exit(1)


def read_config():
    cfg = configparser.ConfigParser()
    cfg.read("config.ini", encoding="utf-8")
    if "jira" not in cfg:
        raise RuntimeError("В config.ini отсутствует секция [jira]")
    j = cfg["jira"]
    return j.get("host"), j.get("username"), j.get("password")


def load_jql_from_args(args):
    if args.jql:
        return args.jql.strip()
    if args.jql_file:
        return Path(args.jql_file).read_text(encoding="utf-8").strip()
    raise RuntimeError("Нужно передать --jql или --jql-file")


def connect_jira(host, username, password, verify_ssl=False):
    return Jira(url=host, username=username, password=password, verify_ssl=verify_ssl)


def fetch_issues_by_jql(jira, jql, fields, expand, page_limit=100, hard_limit=None):
    """
    Забирает все задачи по JQL с пагинацией (startAt).
    """
    # первая страница
    page = jira.jql(jql, fields=fields, expand=expand, limit=page_limit)
    issues = list(page.get("issues", []))
    total = int(page.get("total", len(issues)))

    if hard_limit:
        total = min(total, hard_limit)

    # догружаем остальные страницы
    pages = ceil(total / page_limit)
    for i in tqdm(range(1, pages), desc="📦 Пагинация по JQL"):
        start = i * page_limit
        if hard_limit:
            # не выходим за предел
            left = hard_limit - len(issues)
            if left <= 0:
                break
            limit = min(page_limit, left)
        else:
            limit = page_limit

        more = jira.jql(jql, fields=fields, expand=expand, limit=limit, start=start)
        issues.extend(more.get("issues", []))

    # дедупликат по ключу
    uniq = {it["key"]: it for it in issues if "key" in it}
    return list(uniq.values()), total


def iter_changelog_rows(issue):
    """
    Превращает changelog.issue в записи для CSV: (key, summary, at, author, field, from, to)
    """
    key = issue.get("key")
    fields = issue.get("fields", {})
    summary = fields.get("summary", "")
    changelog = issue.get("changelog", {}) or {}
    histories = changelog.get("histories", []) or []

    for item in histories:
        when = item.get("created")
        author = (item.get("author") or {}).get("displayName") or ""
        for ch in item.get("items", []) or []:
            field = ch.get("field") or ""
            from_s = ch.get("fromString")
            to_s = ch.get("toString")
            yield (key, summary, when, author, field, from_s, to_s)


def main():
    parser = argparse.ArgumentParser(description="Выгрузка пользователей из истории задач по JQL")
    parser.add_argument("--jql", help="JQL строка")
    parser.add_argument("--jql-file", help="Путь к файлу с JQL")
    parser.add_argument("--limit", type=int, default=None, help="Жёсткий лимит задач (для отладки)")
    parser.add_argument("--outfile", default="data/jql_users_activity.csv", help="CSV с подробной активностью")
    parser.add_argument("--usersfile", default="data/jql_users_unique.csv", help="CSV со списком уникальных пользователей")
    parser.add_argument("--verify-ssl", action="store_true", help="Проверять SSL сертификат")
    args = parser.parse_args()

    jql = load_jql_from_args(args)
    host, username, password = read_config()

    print(f"🔗 Jira: {host}")
    print(f"🔎 JQL: {jql}")

    jira = connect_jira(host, username, password, verify_ssl=args.verify_ssl)

    # Те же приёмы что и в статусных скриптах: fields и expand=changelog
    FIELDS = "key,summary"  # минимально необходимые поля
    EXPAND = "changelog"

    issues, total_est = fetch_issues_by_jql(
        jira, jql, fields=FIELDS, expand=EXPAND, page_limit=100, hard_limit=args.limit
    )
    print(f"✅ Получено задач: {len(issues)} (из ~{total_est})")

    Path("data").mkdir(exist_ok=True, parents=True)

    # Подробная активность
    activity_path = Path(args.outfile)
    users_path = Path(args.usersfile)

    users = set()
    rows = []

    for issue in tqdm(issues, desc="🧾 Обрабатываем истории"):
        for row in iter_changelog_rows(issue):
            # row: (key, summary, when, author, field, from, to)
            rows.append(row)
            users.add(row[3].strip())

    # Сортируем по времени (если возможно распарсить)
    def _safe_dt(x):
        try:
            return dtparse(x[2])
        except Exception:
            return datetime.max

    rows.sort(key=_safe_dt)

    # Запись подробной активности
    with activity_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Issue", "Summary", "When", "Author", "Field", "From", "To"])
        for r in rows:
            w.writerow(r)

    # Уникальные пользователи
    users_list = sorted(u for u in users if u)
    with users_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Author"])
        for u in users_list:
            w.writerow([u])

    print(f"📝 Активность записана: {activity_path}")
    print(f"👥 Уникальные пользователи: {len(users_list)} → {users_path}")


if __name__ == "__main__":
    main()
