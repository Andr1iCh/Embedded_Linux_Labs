#!/usr/bin/env python3
"""Збір системних метрик Raspberry Pi та запис журналів у форматі JSON."""

import argparse
import json
import logging
import time
from logging.handlers import WatchedFileHandler
from pathlib import Path

import psutil
from systemd import journal


INTERVAL = 5
TEMP_FILE = Path("/sys/class/thermal/thermal_zone0/temp")


def get_cpu_temp():
    # Читаємо температуру з файла Linux і переводимо тисячні частки градуса у °C.
    try:
        temperature = int(TEMP_FILE.read_text(encoding="utf-8"))
        return round(temperature / 1000, 1)
    except (OSError, ValueError):
        # Записуємо null у JSON, якщо файл недоступний або містить нечислові дані.
        return None


def collect_metrics():
    # Вимірюємо середнє завантаження всіх ядер CPU протягом однієї секунди.
    cpu_usage = psutil.cpu_percent(interval=1)

    # Одним викликом отримуємо відсоток використання і доступний обсяг RAM.
    memory = psutil.virtual_memory()

    # Формуємо один запис. Доступну RAM переводимо з байтів у мебібайти (MiB).
    return {
        "timestamp": time.time(),
        "cpu_usage_pct": cpu_usage,
        "ram_usage_pct": memory.percent,
        "ram_available_mib": round(memory.available / (1024 * 1024), 1),
        "cpu_temp_c": get_cpu_temp(),
        "disk_usage_pct": psutil.disk_usage("/").percent,
    }


def setup_logger(log_file):
    logger = logging.getLogger("SDR_SysMonitor")
    logger.setLevel(logging.INFO)

    # Передаємо повідомлення до journald з ідентифікатором для пошуку журналу.
    logger.addHandler(journal.JournalHandler(SYSLOG_IDENTIFIER="sdr-monitor"))

    # Дописуємо повідомлення у файл. Після ротації обробник відкриє новий файл
    # за тим самим шляхом, тому службу не потрібно перезапускати.
    logger.addHandler(WatchedFileHandler(log_file, encoding="utf-8"))
    return logger


def main():
    # Описуємо параметри запуску та читаємо їхні значення з командного рядка.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true",
                        help="зібрати один запис, вивести JSON і завершити роботу")
    parser.add_argument("--log-file", type=Path,
                        default=Path("/var/log/sdr_monitor/metrics.log"),
                        help="шлях до файла журналу; його каталог має існувати")
    args = parser.parse_args()

    try:
        logger = setup_logger(args.log_file)
        while True:
            # Запам'ятовуємо початок циклу, щоб врахувати час збору метрик.
            started = time.monotonic()
            # Перетворюємо словник у рядок JSON та записуємо його в обидва журнали.
            message = json.dumps(collect_metrics())
            logger.info(message)

            if args.once:
                print(message)
                return 0

            # Віднімаємо час вимірювання від 5 секунд. Збір CPU вже триває 1 с,
            # тому додаткова пауза зазвичай становить приблизно 4 секунди.
            elapsed = time.monotonic() - started
            time.sleep(max(0, INTERVAL - elapsed))
    except KeyboardInterrupt:
        # Завершуємо ручний запуск через Ctrl+C без виведення traceback.
        return 0
    except OSError as error:
        print(f"[ПОМИЛКА] {error}")
        return 1


if __name__ == "__main__":
    # Передаємо код завершення main() операційній системі: 0 — успіх, 1 — помилка.
    raise SystemExit(main())
