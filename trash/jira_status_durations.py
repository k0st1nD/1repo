# coding: utf-8
"""
jira_status_durations.py
---------------------------------------
Считает, сколько времени задачи провели в каждом статусе
по JQL: project = CAMPEIGN and issuetype = "Клиенты ММБ"

Исправления:
- Полная пагинация всех задач по JQL
- Корректная лента статусов: от created -> первый переход (fromString), далее переходы, последний статус до "сейчас"
---------------------------------------
"""

import configparser
import time
from datetime import datetime, timezone
from atlassian import Jira
from pathlib import Path
import csv
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# === настройки ===
JQL = 'project = CAMPEIGN AND issuetype = "Клиенты ММБ" AND resolved >= -13w'
OUTPUT_FILE = Path("data/status_durations_CAMPEIGN.csv")
PAGE_LIMIT = 200  # больше страница = меньше запросов
SLEEP_BETWEEN_ISSUE = 0.15  # секунд паузы между запросами issue?expand=changelog
USE_RESOLUTION_AS_END = False  # если True: «левую» границу последнего статуса берём до resolutiondate (если есть)
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


def dt_parse(date_str: str) -> datetime | None:
    """Парсит дату Jira ISO8601 → datetime (UTC)."""
    if not date_str:
        return None
    try:
        # Jira обычно отдаёт 2025-07-01T12:34:56.789+0300 / 2025-07-01T12:34:56.789Z
        s = date_str.replace("Z", "+00:00")
        if s[-3] == ":" and (len(s) >= 6 and (s[-6] in ["+", "-"])):
            # уже формата +hh:mm
            dt = datetime.fromisoformat(s)
        else:
            # превращаем +0300 -> +03:00 для fromisoformat
            if (len(s) >= 5) and (s[-5] in ["+", "-"]) and s[-2:].isdigit() and s[-5:-2].isdigit():
                s = s[:-2] + ":" + s[-2:]
            dt = datetime.fromisoformat(s)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def build_status_timeline(issue: dict):
    """
    Строит хронологию (status, entered_at, left_at, duration_days) для одной задачи.
    Логика:
      - стартуем от created со статусом из первого перехода .fromString (если есть),
        иначе из текущего fields.status.name;
      - каждый переход "to" — новый статус с новой датой;
      - последний статус длится до now (или resolutiondate, если USE_RESOLUTION_AS_END=True и она есть).
    """
    fields = issue.get("fields", {}) or {}
    created = dt_parse(fields.get("created"))
    resolution_date = dt_parse(fields.get("resolutiondate"))
    cur_status = (fields.get("status") or {}).get("name")

    # собираем смены статусов из changelog
    histories = (issue.get("changelog") or {}).get("histories", []) or []
    changes = []
    for h in histories:
        when = dt_parse(h.get("created"))
        for it in h.get("items", []) or []:
            if it.get("field") == "status":
                changes.append({
                    "when": when,
                    "from": it.get("fromString"),
                    "to": it.get("toString"),
                })

    # если нет вообще дат создания — ничего не считаем
    if not created:
        return []

    changes = [c for c in changes if c["when"] is not None]
    changes.sort(key=lambda x: x["when"])

    # определяем начальный статус на момент created
    if changes:
        initial_status = changes[0]["from"] or cur_status
    else:
        initial_status = cur_status

    # если инициальный статус неизвестен — лучше явно показать как "Unknown"
    if not initial_status:
        initial_status = "Unknown"

    events = []
    # событие входа в начальный статус на момент created
    events.append({"status": initial_status, "when": created})

    # далее — каждое событие смены статуса
    for ch in changes:
        events.append({"status": ch["to"] or "Unknown", "when": ch["when"]})

    # правая граница — либо resolutiondate (если включено и есть), либо текущее время
    right_boundary = resolution_date if (USE_RESOLUTION_AS_END and resolution_date) else datetime.now(timezone.utc)

    # превращаем события в интервалы
    results = []
    for i in range(len(events)):
        st = events[i]["status"]
        entered = events[i]["when"]
        if i + 1 < len(events):
            left = events[i + 1]["when"]
        else:
            left = right_boundary

        if not entered or not left:
            continue
        if left < entered:
            # защита от редких «кривых» дат
            continue

        days = (left - entered).total_seconds() / 86400.0
        results.append((st, entered, left, round(days, 4)))

    return results


def fetch_all_issue_keys(jira: Jira, jql: str) -> list[str]:
    """
    Полная пагинация по JQL. Возвращает список ключей задач.
    """
    keys: list[str] = []
    start = 0
    total = None
    print("[INFO] Загружаем список задач по JQL с пагинацией...")
    while True:
        page = jira.jql(jql, fields="key,created,status,resolutiondate", limit=PAGE_LIMIT, start=start)
        issues = page.get("issues", []) or []
        if total is None:
            total = page.get("total", len(issues))
            print(f"[INFO] Найдено задач: {total}")
        if not issues:
            break

        for it in issues:
            k = it.get("key")
            if k:
                keys.append(k)

        start += PAGE_LIMIT
        if start >= total:
            break

    return keys


def main():
    jira = connect_jira()
    print(f"[INFO] Выполняем JQL: {JQL}")

    # 1) получаем ВСЕ ключи задач по JQL (с пагинацией)
    keys = fetch_all_issue_keys(jira, JQL)
    print(f"[INFO] Ключей получено: {len(keys)}")

    # 2) по каждой задаче отдельно тянем changelog и считаем интервалы
    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    with OUTPUT_FILE.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Issue Key", "Status", "Duration (days)", "Entered", "Left"])

        for idx, key in enumerate(keys, start=1):
            print(f"[{idx}/{len(keys)}] Обрабатываем {key} ...")
            try:
                issue = jira.issue(key, expand="changelog")  # отдельным запросом
                intervals = build_status_timeline(issue)
                if not intervals:
                    print(f"   ⚠ Нет данных по статусам для {key}")
                    continue

                for status, entered, left, days in intervals:
                    w.writerow([
                        key,
                        status,
                        days,
                        entered.strftime("%Y-%m-%d %H:%M:%S"),
                        left.strftime("%Y-%m-%d %H:%M:%S"),
                    ])

            except Exception as e:
                print(f"   ❌ Ошибка {key}: {e}")
                continue

            time.sleep(SLEEP_BETWEEN_ISSUE)

    print(f"\n✅ Готово. Результат сохранён в {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
