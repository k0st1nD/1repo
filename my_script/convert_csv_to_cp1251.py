# coding: utf-8
import argparse
import csv
from pathlib import Path

def sniff_format(sample_bytes: bytes, default_delim=";"):
    sample = sample_bytes.decode("utf-8", errors="ignore")
    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(sample, delimiters=[',',';','\t','|'])
        delimiter = dialect.delimiter
        quotechar = getattr(dialect, "quotechar", '"') or '"'
    except Exception:
        delimiter = default_delim
        quotechar = '"'
    return delimiter, quotechar

def convert_file(src: Path, suffix: str, force_delim: str | None, dry_run: bool=False):
    head = src.read_bytes()[:65536]
    delimiter, quotechar = sniff_format(head)
    if force_delim:
        delimiter = force_delim

    dst = src.with_name(src.stem + suffix + src.suffix)

    if dry_run:
        return dst, 0, delimiter, quotechar

    with src.open("r", encoding="utf-8-sig", newline="") as fin, \
         dst.open("w", encoding="cp1251", errors="replace", newline="") as fout:

        reader = csv.reader(fin, delimiter=delimiter, quotechar=quotechar)
        writer = csv.writer(fout, delimiter=delimiter, quotechar=quotechar, lineterminator="\n")

        rows = 0
        for row in reader:
            writer.writerow(row)
            rows += 1

    return dst, rows, delimiter, quotechar

def main():
    script_dir = Path(__file__).resolve().parent

    ap = argparse.ArgumentParser(description="Конвертирует CSV из UTF-8 в CP1251 для Excel")
    ap.add_argument("--input-dir", default=str(script_dir / "data"),
                    help="Папка с CSV (по умолчанию: <папка_скрипта>/data)")
    ap.add_argument("--suffix", default=".win1251",
                    help="Суффикс новых файлов (по умолчанию: .win1251)")
    ap.add_argument("--force-delim", default=None,
                    help="Принудительный разделитель, напр. ';'")
    ap.add_argument("--recursive", action="store_true",
                    help="Искать рекурсивно во всех подкаталогах")
    ap.add_argument("--dry-run", action="store_true",
                    help="Только показать, что будет сделано, без записи файлов")
    args = ap.parse_args()

    base = Path(args.input_dir)
    print(f"[INFO] Base dir: {base.resolve()}")
    if not base.exists():
        print("[ERROR] Папка не найдена. Укажи корректный --input-dir.")
        return

    patterns = ["*.csv", "*.CSV"]
    files = []
    for pat in patterns:
        files += list(base.rglob(pat) if args.recursive else base.glob(pat))

    print(f"[INFO] Найдено файлов: {len(files)}")
    if not files:
        print("[INFO] CSV-файлы не найдены.")
        return

    made = 0
    for src in sorted(files):
        try:
            dst, rows, delim, quote = convert_file(src, args.suffix, args.force_delim, dry_run=args.dry_run)
            action = "PLAN" if args.dry_run else "WRITE"
            print(f"[{action}] {src} -> {dst.name}  (delim='{delim}', quote='{quote}', rows={rows})")
            made += 1
        except Exception as e:
            print(f"[WARN] Ошибка на {src}: {e}")

    print(f"[INFO] Готово. Обработано файлов: {made}")

if __name__ == "__main__":
    main()
