# coding: utf-8

import configparser
import simplejson as json
from atlassian import Jira
from dateutil.parser import parse as dtparse
from datetime import datetime
from pathlib import Path
import jira_helper

# --- Конфигурация ---
config = configparser.ConfigParser()
config.read("config.ini")

jira_config = config["jira"]
data_prefix = config["statusflow"]['prefix']

# --- Константы ---
BOARD_ID = 12743
START_FROM = datetime(2024, 10, 1)
LIMIT = 50

# --- Jira клиент ---
jira = Jira(
    url=jira_config["host"],
    username=jira_config["username"],
    password=jira_config["password"],
    verify_ssl=False
)

# --- Получение всех закрытых спринтов с доски ---
print(f"⏳ Загружаем спринты с доски {BOARD_ID}...")
all_sprints = []
start = 0
is_last = False

while not is_last:
    page = jira.get_all_sprints_from_board(board_id=BOARD_ID, state="closed", start=start)
    all_sprints += page["values"]
    is_last = page["isLast"]
    start += LIMIT

print(f"🔍 Найдено спринтов всего: {len(all_sprints)}")

# --- Фильтрация по originBoardId и дате ---
filtered = []
for s in all_sprints:
    if s.get("originBoardId") != BOARD_ID:
        continue
    if "startDate" not in s:
        continue

    start_date = dtparse(s["startDate"]).replace(tzinfo=None)
    if start_date >= START_FROM:
        activated_date = s.get("activatedDate") or s.get("startDate")
        complete_date = s.get("completeDate") or s.get("endDate")
        filtered.append({
            "id": s["id"],
            "name": s["name"],
            "startDate": s.get("startDate"),
            "endDate": s.get("endDate"),
            "activatedDate": activated_date,
            "completeDate": complete_date,
            "state": s.get("state"),
        })

print(f"✅ Отфильтровано спринтов с originBoardId == {BOARD_ID} и даты {START_FROM.date()}: {len(filtered)}")

# --- Дополнительный вывод для проверки ---
print("\n📋 Список отфильтрованных спринтов:")
for idx, s in enumerate(filtered, 1):
    start_str = dtparse(s["startDate"]).strftime("%Y-%m-%d") if s["startDate"] else "—"
    print(f"{idx:3}. {start_str} — {s['name']}")

# --- Сохранение ---
Path("data").mkdir(exist_ok=True)
output_file = f"data/{data_prefix}.1.sprints.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(filtered, f, indent=2, ensure_ascii=False)

print(f"\n📁 Спринты сохранены в {output_file}")
