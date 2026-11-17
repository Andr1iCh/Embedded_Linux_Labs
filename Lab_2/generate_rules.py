#!/usr/bin/env python3
"""Запускати на RPi: python3 generate_rules.py /dev/ttyUSB0."""

import sys
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        print("Використання: python3 generate_rules.py /dev/ttyUSB0")
        return 1

    device = Path(sys.argv[1]).resolve()
    if not device.exists() or not device.name.startswith("ttyUSB"):
        print("Потрібен наявний USB-UART /dev/ttyUSB...")
        return 1

    # Знаходимо батьківський каталог із файлом idVendor у /sys.
    # З цього каталогу далі зчитуємо VID, PID і серійний номер адаптера.
    tty = Path("/sys/class/tty") / device.name / "device"
    usb = next((p for p in tty.resolve().parents if (p / "idVendor").exists()), None)
    if usb is None:
        print("Не вдалося знайти USB-батька пристрою")
        return 1

    vid = (usb / "idVendor").read_text().strip()
    pid = (usb / "idProduct").read_text().strip()
    serial_file = usb / "serial"
    serial = serial_file.read_text().strip() if serial_file.exists() else ""
    # Додаємо до правила перевірку серійного номера, якщо він є.
    # Якщо номера немає, додаємо перевірку USB-порту підключення.
    if serial:
        if any(c in serial for c in '\\"*?[]\n\r'):
            print("Незвичний серійний номер: перевірте правило вручну")
            return 1
        binding = f'ATTRS{{serial}}=="{serial}"'
        print(f"Прив'язка за серійним номером: {serial}")
    else:
        binding = f'KERNELS=="{usb.name}"'
        print(f"Серійного номера немає. Використовуйте той самий USB-порт: {usb.name}")

    rule = (f'SUBSYSTEM=="tty", KERNEL=="ttyUSB*", ATTRS{{idVendor}}=="{vid}", '
            f'ATTRS{{idProduct}}=="{pid}", {binding}, '
            'SYMLINK+="uart_compass", MODE="0666"\n')
    # Читаємо файл правил і видаляємо рядок попереднього UART-правила.
    # Записуємо решту вмісту назад у файл та додаємо нове UART-правило.
    output = Path(__file__).with_name("99-radio-monitor.rules")
    lines = output.read_text(encoding="utf-8").splitlines(keepends=True)
    lines = [line for line in lines if not line.startswith('SUBSYSTEM=="tty"')]
    output.write_text("".join(lines) + rule, encoding="utf-8")
    print(f"VID={vid}, PID={pid}\n{rule}Збережено: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
