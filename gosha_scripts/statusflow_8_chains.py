# coding: utf-8

import json
import configparser
from pathlib import Path
from collections import defaultdict, Counter

# ==========================
# Конфигурация
# ==========================

config = configparser.ConfigParser()
config.read("config.ini")
data_prefix = config["statusflow"]["prefix"]

INPUT_FILE = f"data/{data_prefix}.3.processed.json"
OUTPUT_FILE = f"data/{data_prefix}.8.chains.json"
REPORT_FILE = f"data/{data_prefix}.8.chains_report.md"

Path("data").mkdir(exist_ok=True, parents=True)

# ==========================
# Загрузка
# ==========================

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    issues = json.load(f)

print(f"📥 Загружено задач: {len(issues)}")

# ==========================
# Подсчёт частот цепочек статусов
# ==========================

chains_by_type = defaultdict(list)

for issue in issues:
    issue_type = issue.get("type", "Unknown")
    chain = issue.get("statusChain")
    if not chain or len(chain) < 2:
        continue
    _ = " → ".join(chain)
    if 'Исследование' in _ and issue_type == 'Middle Task':
        print(issue)

    chains_by_type[issue_type].append(" → ".join(chain))

summary = {}
report_lines = ["# 🔗 Частоты уникальных цепочек статусов по типам задач\n"]

for issue_type, chains in chains_by_type.items():
    report_lines.append(f"\n## 🧩 {issue_type}")

    counter = Counter(chains)
    total = sum(counter.values())

    # Сохраняем в JSON
    summary[issue_type] = [
        {"chain": chain, "count": count, "share": round(count / total * 100, 1)}
        for chain, count in counter.most_common()
    ]

    # Пишем в Markdown
    report_lines.append("| № | Цепочка статусов | Кол-во | Доля (%) |")
    report_lines.append("|---|------------------|---------|-----------|")

    for i, (chain, count) in enumerate(counter.most_common(), start=1):
        report_lines.append(f"| {i} | {chain} | {count} | {count / total * 100:.1f}% |")

    # 👥 Активность по ролям (по аналогии с прежним отчётом)
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
