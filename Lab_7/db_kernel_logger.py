#!/usr/bin/env python3
"""Запис тестової телеметрії SDR у SQLite та сповіщення ядра Linux."""

import sqlite3
import time
from pathlib import Path


DB_FILE = Path(__file__).with_name("sdr_telemetry.db")
KERNEL_DEV = "/dev/sdr_alert"
ALERT_THRESHOLD_RSSI = -20.0


def init_db(connection):
    # Створюємо таблицю під час першого запуску. Наступні запуски зберігають попередні записи.
    connection.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            frequency_mhz REAL NOT NULL,
            rssi_dbm REAL NOT NULL
        )
    """)


def log_signal(connection, frequency, rssi):
    # Передаємо значення окремо від SQL-запиту та зберігаємо запис у базі.
    connection.execute(
        "INSERT INTO signals (timestamp, frequency_mhz, rssi_dbm) VALUES (?, ?, ?)",
        (time.time(), frequency, rssi),
    )
    connection.commit()
    print(f"[БД] Записано {frequency:g} МГц, RSSI {rssi:g} dBm")

    # При -20 dBm і слабшому сигналі достатньо запису в базі.
    if rssi <= ALERT_THRESHOLD_RSSI:
        return True

    # Відкриваємо наявний пристрій і передаємо один байт без переносу рядка.
    try:
        with open(KERNEL_DEV, "r+b", buffering=0) as device:
            device.write(b"1")
    except OSError as error:
        print(f"[ПОМИЛКА] Запис у БД збережено. Не вдалося записати в {KERNEL_DEV}: {error}")
        return False

    print(f"[ТРИВОГА] RSSI перевищив {ALERT_THRESHOLD_RSSI:g} dBm. Байтом '1' сповіщено ядро.")
    return True


def main():
    try:
        connection = sqlite3.connect(DB_FILE)
        try:
            init_db(connection)
            # Імітуємо два вимірювання: слабший сигнал і сигнал вище порогу.
            log_signal(connection, 101.5, -45.0)
            alert_ok = log_signal(connection, 433.92, -12.5)
        finally:
            connection.close()
    except sqlite3.Error as error:
        print(f"[ПОМИЛКА БД] {error}")
        return 1

    return 0 if alert_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
