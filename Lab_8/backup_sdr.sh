#!/usr/bin/env bash
set -euo pipefail

# Нові каталоги та архіви доступні лише користувачу, який запускає скрипт.
umask 077
export LC_ALL=C

BACKUP_DIR="${SDR_BACKUP_DIR:-/var/backups/sdr_system}"
PROJECT_DIR="${SDR_PROJECT_DIR:-$HOME}"
ETC_DIR="${SDR_ETC_DIR:-/etc}"
LOG_DIR="${SDR_LOG_DIR:-/var/log/sdr_monitor}"
DB_FILE="$PROJECT_DIR/Lab_7/sdr_telemetry.db"
ARCHIVE_NAME="sdr_backup_$(date +%Y%m%d_%H%M%S).tar.gz"

fail() {
    printf '[ПОМИЛКА] %s\n' "$*" >&2
    exit 1
}

config_files=(
    "$ETC_DIR/udev/rules.d/99-radio-monitor.rules"
    "$ETC_DIR/systemd/system/sdr_web.service"
)
web_files=(
    "$PROJECT_DIR/Lab_4/sdr_web_app.py"
    "$PROJECT_DIR/Lab_4/index.html"
    "$PROJECT_DIR/Lab_4/requirements.txt"
)
required_files=("${config_files[@]}" "${web_files[@]}" "$DB_FILE")

printf '[%s] Початок резервного копіювання\n' "$(date '+%F %T')"
for file in "${required_files[@]}"; do
    [[ -f "$file" && -r "$file" ]] || fail "Немає доступного файла: $file"
done

optional_files=(
    "$ETC_DIR/systemd/system/sdr-monitor.service"
    "$ETC_DIR/logrotate.d/sdr-monitor"
    "$LOG_DIR/metrics.log"
    "$PROJECT_DIR"/Lab_{2,4,6,7,8}/README.md
)

# Враховуємо доступні додаткові файли й WAL, якщо база зараз його використовує.
size_files=("${required_files[@]}")
for file in "${optional_files[@]}" "$DB_FILE-wal"; do
    if [[ -f "$file" && -r "$file" ]]; then
        size_files+=("$file")
    fi
done

mkdir -p -- "$BACKUP_DIR"
# du рахує розмір файлів, а df показує вільне місце на диску з каталогом копій.
used_kib=$(du -k --apparent-size -- "${size_files[@]}" | awk '{sum += $1} END {print sum}')
free_kib=$(df -Pk -- "$BACKUP_DIR" | awk 'NR == 2 {print $4}')
# Резервуємо місце для тимчасових копій, архіву і ще 10 MiB запасу.
needed_kib=$((used_kib * 2 + 10240))
printf 'Вільно: %s KiB. Потрібно: %s KiB.\n' "$free_kib" "$needed_kib"
(( free_kib >= needed_kib )) || fail "Недостатньо місця в $BACKUP_DIR"

work_dir=$(mktemp -d -- "$BACKUP_DIR/.sdr-backup.XXXXXXXX")
# При завершенні видаляємо лише тимчасовий каталог цього запуску.
trap 'rm -rf -- "$work_dir"' EXIT
stage="$work_dir/files"
mkdir -p -- "$stage"/{config,web,database,logs,reports}

cp -- "${config_files[@]}" "$stage/config/"
cp -- "${web_files[@]}" "$stage/web/"
# SQLite створює узгоджену копію бази, навіть коли дані ще є в WAL.
(
    cd "$stage/database"
    sqlite3 -readonly -cmd '.timeout 5000' "$DB_FILE" '.backup sdr_telemetry.db'
)

for file in "${optional_files[@]}"; do
    if [[ ! -f "$file" || ! -r "$file" ]]; then
        printf '[ПРОПУСК] %s\n' "$file"
        continue
    fi
    case "$file" in
        */README.md)
            lab_dir=$(basename "$(dirname "$file")")
            cp -- "$file" "$stage/reports/$lab_dir.md"
            ;;
        "$LOG_DIR/metrics.log") cp -- "$file" "$stage/logs/" ;;
        *) cp -- "$file" "$stage/config/" ;;
    esac
done

# Спершу створюємо і перевіряємо архів. Лише потім публікуємо готовий файл.
archive="$BACKUP_DIR/$ARCHIVE_NAME"
tar -czf "$work_dir/$ARCHIVE_NAME" -C "$stage" config web database logs reports
tar -tzf "$work_dir/$ARCHIVE_NAME" >/dev/null
# Готовий файл з'являється за один крок. Якщо таке ім'я вже є, ln не перезапише його.
ln -T -- "$work_dir/$ARCHIVE_NAME" "$archive"
printf '[УСПІХ] Архів створено: %s\n' "$archive"

# Чистимо лише архіви цієї лабораторної після успішного створення нового.
find "$BACKUP_DIR" -maxdepth 1 -type f \
    -name 'sdr_backup_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_[0-9][0-9][0-9][0-9][0-9][0-9].tar.gz' \
    -mmin +20160 -print -delete

# За потреби cron може передавати готовий архів на окремий Linux-сервер.
if [[ -n "${SDR_REMOTE:-}" ]]; then
    rsync -at -e 'ssh -o BatchMode=yes -o ConnectTimeout=10' -- "$archive" "$SDR_REMOTE"
    printf '[УСПІХ] Копію передано: %s\n' "$SDR_REMOTE"
fi
printf '[%s] Резервне копіювання завершено\n' "$(date '+%F %T')"
