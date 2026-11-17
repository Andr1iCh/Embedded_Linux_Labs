#!/usr/bin/env python3
"""Записувати телеметрію Raspberry Pi та керувати світлодіодом за температурою."""

import argparse
import csv
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import gpiod
from gpiod.line import Direction, Value


INTERVAL_SECONDS = 5
LED_LINE = 18  
TEMPERATURE_FILE = Path("/sys/class/thermal/thermal_zone0/temp")
CPU_FILE = Path("/proc/stat")
MEMORY_FILE = Path("/proc/meminfo")
CSV_HEADER = ["Timestamp", "Temp", "CPU_Load", "RAM_Usage"]


def read_temperature():
    """Прочитати температуру ядра: у файлі вона записана в тисячних частках °C."""
    return int(TEMPERATURE_FILE.read_text().strip()) / 1000


def read_cpu_times():
    """Повернути накопичений загальний час CPU та час його простою."""
    # Перший рядок /proc/stat містить сумарні лічильники для всіх ядер.
    first_line = CPU_FILE.read_text().splitlines()[0]
    fields = first_line.split()
    if fields[0] != "cpu" or len(fields) < 9:
        raise ValueError("Неочікуваний формат /proc/stat")

    # Порядок полів: user, nice, system, idle, iowait, irq, softirq, steal.
    times = [int(value) for value in fields[1:9]]
    total = sum(times)
    # Час очікування вводу-виводу (iowait) теж рахуємо як простій CPU.
    idle = times[3] + times[4]
    return total, idle


def calculate_cpu_load(previous, current):
    """Обчислити відсоток зайнятості CPU між двома вимірюваннями."""
    # Самі лічильники накопичувальні, тому беремо різницю між знімками.
    total_delta = current[0] - previous[0]
    idle_delta = current[1] - previous[1]
    if total_delta <= 0:
        raise ValueError("Лічильники CPU не зросли")
    return 100 * (total_delta - idle_delta) / total_delta


def read_ram_usage():
    """Оцінити використання RAM за MemTotal і MemAvailable, без swap."""
    values = {}
    # У /proc/meminfo багато полів; зберігаємо тільки потрібні два.
    for line in MEMORY_FILE.read_text().splitlines():
        key, separator, rest = line.partition(":")
        if separator and key in ("MemTotal", "MemAvailable"):
            values[key] = int(rest.split()[0])  # Обидва значення подано в кБ.

    total = values["MemTotal"]
    available = values["MemAvailable"]
    if total <= 0:
        raise ValueError("MemTotal має бути додатним")
    return 100 * (total - available) / total


def stop_monitor(_signal_number, _frame):
    """Перетворити SIGTERM від systemd на звичайне завершення монітора."""
    raise KeyboardInterrupt


def monitor(csv_path, gpio_chip, threshold):
    """Утримувати GPIO та дописувати один рядок CSV кожні 5 секунд."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    # Запитуємо GPIO як вихід і тримаємо лінію зайнятою, поки працює цикл.
    # Початковий стан LED — вимкнений.
    with gpiod.request_lines(
        gpio_chip,
        consumer="sys-monitor",
        config={
            LED_LINE: gpiod.LineSettings(
                direction=Direction.OUTPUT, output_value=Value.INACTIVE
            )
        },
    ) as led:
        try:
            # Для відсотка CPU потрібні два знімки лічильників.
            previous_cpu = read_cpu_times()

            # Режим "a" дописує дані; заголовок потрібен лише порожньому файлу.
            with csv_path.open("a", newline="", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                if csv_file.tell() == 0:
                    writer.writerow(CSV_HEADER)
                    csv_file.flush()

                while True:
                    # Другий знімок робимо після паузи, щоб виміряти CPU за інтервал.
                    time.sleep(INTERVAL_SECONDS)
                    current_cpu = read_cpu_times()
                    cpu_load = calculate_cpu_load(previous_cpu, current_cpu)
                    previous_cpu = current_cpu

                    temperature = read_temperature()
                    ram_usage = read_ram_usage()

                    # Порівнюємо поточну температуру з порогом та змінюємо LED.
                    led.set_value(
                        LED_LINE,
                        Value.ACTIVE if temperature > threshold else Value.INACTIVE,
                    )

                    # Час у CSV записуємо в UTC, числа — з двома знаками після крапки.
                    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
                    writer.writerow(
                        [timestamp, f"{temperature:.2f}", f"{cpu_load:.2f}", f"{ram_usage:.2f}"]
                    )
                    csv_file.flush()  # Передаємо рядок з буфера Python у файлову систему.
        finally:
            # Перед виходом із "with" вимикаємо LED; "with" звільнить GPIO.
            led.set_value(LED_LINE, Value.INACTIVE)


def main():
    """Зчитати параметри запуску та повідомити системі про результат роботи."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chip", default="/dev/gpiochip0", help="Контролер із GPIO18")
    parser.add_argument("--csv", type=Path, default=Path("telemetry.csv"))
    parser.add_argument("--threshold", type=float, default=60.0, help="Поріг LED у °C")
    args = parser.parse_args()

    # Під час зупинки служби systemd надсилає SIGTERM.
    signal.signal(signal.SIGTERM, stop_monitor)
    try:
        monitor(args.csv, args.chip, args.threshold)
    except KeyboardInterrupt:
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(f"Монітор зупинено: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
