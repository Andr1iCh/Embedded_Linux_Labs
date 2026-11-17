#!/usr/bin/env python3
"""Перевірка udev-посилань і UART: loopback або читання з пристрою."""

import argparse
import os
import stat
from pathlib import Path

import serial


def check_device_access(device_path, expected_type):
    path = Path(device_path)
    if not path.is_symlink():
        print(f"[ПОМИЛКА] {path}: немає символічного посилання")
        return False
    if not path.exists():
        print(f"[ПОМИЛКА] {path}: посилання веде на відсутній пристрій")
        return False

    info = path.stat()  # stat() перевіряє ціль посилання, а не саме посилання.
    mode = stat.S_IMODE(info.st_mode)
    if not stat.S_ISCHR(info.st_mode):
        print(f"[ПОМИЛКА] {path}: ціль не є символьним пристроєм")
        return False
    if expected_type == "uart" and not path.resolve().name.startswith("ttyUSB"):
        print(f"[ПОМИЛКА] {path}: очікувався USB-UART /dev/ttyUSB...")
        return False
    if expected_type == "sdr" and not str(path.resolve()).startswith("/dev/bus/usb/"):
        print(f"[ПОМИЛКА] {path}: очікувався USB-вузол SDR")
        return False
    if mode != 0o666 or not os.access(path, os.R_OK | os.W_OK):
        print(f"[ПОМИЛКА] {path}: MODE={mode:04o}, потрібні 0666 і доступ R/W")
        return False
    print(f"[ОК] {path} -> {path.resolve()}, MODE={mode:04o}, доступ R/W")
    return True


def test_uart(port_path, baudrate, loopback):
    try:
        # Таймаут обмежує очікування, якщо RX нічого не отримує.
        with serial.Serial(port_path, baudrate, timeout=2, write_timeout=2) as port:
            if loopback:
                # TX і RX PL2303 потрібно з'єднати перемичкою.
                port.reset_input_buffer()
                expected = b"UART test\r\n"
                port.write(expected)
                received = port.read(len(expected))
                print(f"TX: {expected!r}; RX: {received!r}")
                if received != expected:
                    print("[ПОМИЛКА] Loopback: отримані байти не збігаються з переданими")
                    return False
                print("[ОК] Loopback: усі тестові байти повернулися")
            else:
                # Для справжнього компаса: він має сам передавати дані.
                received = port.read(10)
                if not received:
                    print("[ПОМИЛКА] Порт відкрито, але за 2 секунди даних немає")
                    return False
                print(f"[ОК] Отримано байти: {received.hex()}")
        return True
    except (serial.SerialException, OSError) as error:
        print(f"[ПОМИЛКА] UART: {error}")
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="/dev/uart_compass")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--loopback", action="store_true", help="тест TX-RX перемичкою")
    parser.add_argument("--skip-sdr", action="store_true", help="явно пропустити відсутній SDR")
    args = parser.parse_args()

    uart_ok = check_device_access(args.port, "uart")
    if uart_ok:
        uart_ok = test_uart(args.port, args.baud, args.loopback)

    if args.skip_sdr:
        print("[ПРОПУСК] SDR відсутній; його правило та доступ не перевірено")
        sdr_ok = True
    else:
        sdr_ok = check_device_access("/dev/sdr_primary", "sdr")
    success = uart_ok and sdr_ok
    print("[РЕЗУЛЬТАТ] Обрані перевірки пройдено" if success else "[РЕЗУЛЬТАТ] Є помилки")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
