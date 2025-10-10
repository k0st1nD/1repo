# statusflow_2_load_issues.py
# coding: utf-8

import configparser
import simplejson as json
from atlassian import Jira
from pathlib import Path
from dateutil.parser import parse as dtparse
from math import ceil
from tqdm import tqdm
import jira_helper

# --- Конфигурация ---
config = configparser.ConfigParser()
config.read("config.ini")

jira_config = config["jira"]
data_prefix = config["statusflow"].get("prefix", "statusflow")

# --- Загрузка спринтов из предыдущего шага ---
with open(f"data/{data_prefix}.1.sprints.json", "r", encoding="utf-8") as f:
    sprint_data = json.load(f)

sprint_ids = [s["id"] for s in sprint_data]
print(f"🔄 Спринты для анализа: {len(sprint_ids)} шт.")

# --- Jira клиент ---
jira = Jira(
    url=jira_config["host"],
    username=jira_config["username"],
    password=jira_config["password"],
    verify_ssl=False
)

# --- Получение задач через JQL ---
LIMIT = 100
FIELDS = "key,summary,issuetype,status,created,resolutiondate,assignee,customfield_10375,customfield_10376"
EXPAND = "changelog"

issues = []
for sprint_id in tqdm(sprint_ids, desc="📦 Загрузка задач по спринтам"):
    jql = f"Sprint = {sprint_id} and issuetype in standardIssueTypes() and statusCategory = Done"
    page = jira.jql(jql, fields=FIELDS, expand=EXPAND, limit=LIMIT)
    issues.extend(page["issues"])
    total = page["total"]
    for i in range(1, ceil(total / LIMIT)):
        offset = i * LIMIT
        page_more = jira.jql(jql, fields=FIELDS, expand=EXPAND, limit=LIMIT, start=offset)
        issues.extend(page_more["issues"])

print(f"✅ Загружено задач всего: {len(issues)}")
unique_issues = {issue["key"]: issue for issue in issues if "key" in issue}
issues = list(unique_issues.values())
print(f"✅ Уникальных задач всего: {len(issues)}")
# --- Сохранение "сырых" задач ---
Path("data").mkdir(exist_ok=True)
output_file = f"data/{data_prefix}.2.issues.raw.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(issues, f, indent=2, ensure_ascii=False)

print(f"📁 Задачи сохранены в {output_file}")