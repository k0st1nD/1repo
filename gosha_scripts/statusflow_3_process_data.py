# coding: utf-8

import json
import os
from datetime import datetime
from dateutil.parser import parse as dtparse
from atlassian import Jira
import configparser
import jira_helper

# ==========================
# Конфигурация
# ==========================

config = configparser.ConfigParser()
config.read("config.ini")

jira_config = config["jira"]
data_prefix = config["statusflow"]["prefix"]

JIRA = Jira(
    url=jira_config["host"],
    username=jira_config["username"],
    password=jira_config["password"],
    verify_ssl=False
)

ISSUES_FILE = f"data/{data_prefix}.2.issues.raw.json"
SPRINTS_FILE = f"data/{data_prefix}.1.sprints.json"
OUTPUT_FILE = f"data/{data_prefix}.3.processed.json"
EPIC_CACHE_FILE = "data/epic_cache.json"

# ==========================
# Настройки и роли
# ==========================

TEAM_ROLES = {
    "Хоменков Григорий Вячеславович": "PO",
    "Бровкин Михаил Всеволодович": "BA",
    "Тарабанько Татьяна Валерьевна": "BA",
    "Яковец Ольга Сергеевна": "Design",
    "Афанасьев Алексей Иванович": "Java",
    "Балмашов Сергей Анатольевич": "System Analysis",
    "Волнейко Василий Александрович": "QA Fullstack",
    "Колос Владислав Игоревич": "JS",
    "Кудимов Илья Александрович": "Java",
    "Оролбаева Токтобубу Токтоналиевна": "QA Fullstack",
    "Цыганков Николай Валерьевич": "System Analysis",
    "Кулаева Наталия Игоревна [X]": "System Analysis",
    "Гаврилов Вячеслав Сергеевич [X]": "Design",
}

# ==========================
# Загрузка кэша эпиков
# ==========================

if os.path.exists(EPIC_CACHE_FILE):
    with open(EPIC_CACHE_FILE, "r", encoding="utf-8") as f:
        EPIC_CACHE = json.load(f)
else:
    EPIC_CACHE = {}

def get_role(name: str):
    if not name:
        return "unknown"
    for k, v in TEAM_ROLES.items():
        if name.strip().lower() == k.lower():
            return v
    return "unknown"

def get_epic_data(epic_key: str):
    """Получаем данные об эпике с кэшем"""
    if not epic_key:
        return None
    if epic_key in EPIC_CACHE:
        return EPIC_CACHE[epic_key]

    print(f"📡 Загружаем эпик {epic_key}...")
    epic = JIRA.issue(epic_key)

    fields = epic["fields"]
    epic_data = {
        "key": epic_key,
        "summary": fields.get("summary"),
        "created": fields.get("created"),
        "plannedStart": fields.get("customfield_21675"),
        "plannedEnd": fields.get("customfield_21471"),
        "duedate": fields.get("duedate"),
    }

    EPIC_CACHE[epic_key] = epic_data

    # обновляем кэш на диск
    with open(EPIC_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(EPIC_CACHE, f, indent=2, ensure_ascii=False)

    return epic_data

# ==========================
# Загрузка задач и обработка
# ==========================

print("📥 Загружаем задачи...")
with open(ISSUES_FILE, "r", encoding="utf-8") as f:
    issues = json.load(f)

print(f"🔍 Загружено задач: {len(issues)}")

processed = []

for issue in issues:
    key = issue["key"]
    fields = issue["fields"]
    changelog = issue.get("changelog", {}).get("histories", [])

    # --- Базовая информация ---
    assignee = fields.get("assignee", {}).get("displayName")
    issue_type = fields.get("issuetype", {}).get("name")
    status = fields.get("status", {}).get("name")
    summary = fields.get("summary")
    epic_key = fields.get("customfield_10376")
    created = fields.get("created")

    # --- Эпик ---
    epic_info = get_epic_data(epic_key) if epic_key else None

    # --- История изменений ---
    status_flow = []
    assignee_changes = []
    sprint_changes = []

    for item in changelog:
        author = item.get("author", {}).get("displayName")
        author_role = get_role(author)
        when = item.get("created")

        for change in item.get("items", []):
            field = change.get("field", "").lower()

            # смена статуса
            if field == "status":
                from_status = change.get("fromString")
                to_status = change.get("toString")

                if to_status.lower() == 'исследование':
                    print(key, summary)

                # # если это первый переход и from отсутствует — создаем стартовый статус
                # if not status_flow and not from_status and to_status:
                #     # добавляем искусственный "начальный" шаг, чтобы выровнять цепочку
                #     status_flow.append({
                #         "from": None,
                #         "to": from_status or "Created",
                #         "by": author,
                #         "by_role": author_role,
                #         "at": created
                #     })

                status_flow.append({
                    "from": from_status,
                    "to": to_status,
                    "by": author,
                    "by_role": author_role,
                    "at": when
                })

            # смена исполнителя
            elif field == "assignee":
                assignee_changes.append({
                    "from": change.get("fromString"),
                    "to": change.get("toString"),
                    "by": author,
                    "by_role": author_role,
                    "at": when
                })

            # смена спринта
            elif field == "sprint":
                sprint_changes.append({
                    "from": change.get("fromString", ""),
                    "to": change.get("toString", ""),
                    "by": author,
                    "by_role": author_role,
                    "at": when
                })

    # --- формируем цепочку статусов ---
    status_flow_sorted = sorted(status_flow, key=lambda x: dtparse(x["at"]))
    status_chain = []

    # добавляем начальный статус (если известен)
    if status_flow_sorted:
        first_from = status_flow_sorted[0].get("from") or fields.get("status", {}).get("name")
        if first_from:
            status_chain.append(first_from)

        for s in status_flow_sorted:
            to_status = s.get("to")
            # избегаем дубликатов подряд
            if to_status and (not status_chain or status_chain[-1] != to_status):
                status_chain.append(to_status)

    processed.append({
        "key": key,
        "summary": summary,
        "type": issue_type,
        "status": status,
        "assignee": assignee,
        "role": get_role(assignee),
        "statusFlow": status_flow_sorted,
        "statusChain": status_chain,  # <--- вот это новое поле
        "assigneeChanges": assignee_changes,
        "sprintChanges": sprint_changes,
        "epic": epic_info
    })

# ==========================
# Сохранение
# ==========================

os.makedirs("data", exist_ok=True)
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(processed, f, indent=2, ensure_ascii=False)

print(f"\n✅ Обработка завершена. Сохранено {len(processed)} задач в {OUTPUT_FILE}")
