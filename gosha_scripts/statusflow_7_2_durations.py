# coding: utf-8

import json
import configparser
import numpy as np
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime

# ==========================
# Конфигурация
# ==========================

config = configparser.ConfigParser()
config.read("config.ini")
data_prefix = config["statusflow"]["prefix"]

INPUT_FILE = f"data/{data_prefix}.3.processed.json"
OUTPUT_FILE = f"data/{data_prefix}.7.2.durations.json"
REPORT_FILE = f"data/{data_prefix}.7.2.durations_report.md"

Path("data").mkdir(exist_ok=True, parents=True)

# ==========================
# Загрузка
# ==========================

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    issues = json.load(f)

print(f"📥 Загружено задач: {len(issues)}")

# ==========================
# Подсчёт длительностей переходов
# ==========================

def parse_jira_date(s: str):
    """Преобразует JIRA-дату в ISO-совместимую."""
    if not s:
        return None
    if len(s) >= 26 and (s[-5] in ['+', '-']) and s[-2] != ':':
        s = s[:-2] + ':' + s[-2:]
    try:
        return datetime.fromisoformat(s.replace('Z', '+00:00'))
    except Exception:
        return None

durations_by_type = defaultdict(lambda: defaultdict(list))

for issue in issues:
    issue_type = issue.get("type", "Unknown")
    flow = issue.get("statusFlow", [])
    if not flow or len(flow) < 2:
        continue

    # сортируем историю по времени
    flow_sorted = sorted(flow, key=lambda x: x.get("at") or "")

    # идём по всем парам подряд, включая первую (Created → Backlog)
    for i in range(1, len(flow_sorted)):
        prev = flow_sorted[i - 1]
        curr = flow_sorted[i]

        t1 = parse_jira_date(prev.get("at"))
        t2 = parse_jira_date(curr.get("at"))
        if not t1 or not t2:
            continue

        delta_days = (t2 - t1).total_seconds() / 86400
        if delta_days <= 0 or delta_days > 365:
            continue  # фильтр аномалий

        # считаем, сколько времени задача провела в статусе prev["to"]
        key = (prev["to"], curr["to"])
        durations_by_type[issue_type][key].append(delta_days)

print(f"✅ Собрано пар: {sum(len(v) for v in durations_by_type.values())}")

# ==========================
# Агрегация статистики
# ==========================

summary = {}
report_lines = ["# ⏱ Среднее время переходов по типам задач\n"]

for issue_type, pairs in durations_by_type.items():
    report_lines.append(f"\n## 🧩 {issue_type}")
    report_lines.append("| Из статуса | В статус | Кол-во | Среднее (дн) | 85-й перц. | 95-й перц. |")
    report_lines.append("|-------------|-----------|---------|---------------|-------------|-------------|")

    stats = {}
    for (frm, to), values in pairs.items():
        arr = np.array(values)
        stats[f"{frm} → {to}"] = {
            "count": len(values),
            "mean": float(np.mean(arr)),
            "p85": float(np.percentile(arr, 85)),
            "p95": float(np.percentile(arr, 95)),
        }

        report_lines.append(
            f"| {frm} | {to} | {len(values)} | {np.mean(arr):.1f} | {np.percentile(arr,85):.1f} | {np.percentile(arr,95):.1f} |"
        )

    summary[issue_type] = stats

    # ==========================
    # 👥 Активность по ролям для этого типа задачи
    # ==========================
    role_counter = Counter()
    for issue in issues:
        if issue.get("type") != issue_type:
            continue
        for h in issue.get("statusFlow", []):
            role = h.get("by_role", "unknown")
            role_counter[role] += 1

    if role_counter:
        report_lines.append(f"\n\n### 👥 Активность по ролям ({issue_type})")
        report_lines.append("| Роль | Кол-во переходов |")
        report_lines.append("|------|------------------|")
        for role, count in sorted(role_counter.items(), key=lambda x: -x[1]):
            report_lines.append(f"| {role} | {count} |")


# ==========================
# Сохранение
# ==========================

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

Path(REPORT_FILE).write_text("\n".join(report_lines), encoding="utf-8")

print(f"\n✅ Расчёт завершён.")
print(f"📊 JSON сохранён: {OUTPUT_FILE}")
print(f"📝 Отчёт сохранён: {REPORT_FILE}")
