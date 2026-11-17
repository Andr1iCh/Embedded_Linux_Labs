#!/usr/bin/env python3
"""Діагностика мережі Linux, перевірка ICMP і заданих TCP-портів."""

import argparse
import ipaddress
import socket
import subprocess


def run_command(command):
    # Виконуємо команду та отримуємо її стандартний вивід як текст.
    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    # Ненульовий код завершення перетворюємо на виняток із текстом помилки команди.
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(command)}: {result.stderr.strip()}")
    # Повертаємо вивід без пробілів і перенесень рядка на його початку та в кінці.
    return result.stdout.strip()


def show_command(title, command):
    # Виводимо заголовок і результат команди; отриманий текст повертаємо для аналізу.
    print(f"\n=== {title} ===")
    output = run_command(command)
    print(output if output else "Немає записів.")
    return output


def find_gateway(routes):
    # Знаходимо адресу після слова via у першому придатному default-маршруті.
    for line in routes.splitlines():
        # Розділяємо рядок маршруту на поля за пробілами.
        fields = line.split()
        if "via" in fields:
            index = fields.index("via")
            # Перевіряємо наявність наступного поля та повертаємо адресу шлюзу.
            if index + 1 < len(fields):
                return fields[index + 1]
    # Якщо адресу шлюзу не знайдено, повертаємо None.
    return None


def parse_neighbors(output):
    # Вибираємо IP, MAC і стан із кожного рядка таблиці сусідів.
    neighbors = []
    for line in output.splitlines():
        fields = line.split()
        # Пропускаємо порожні рядки, щоб не звертатися до відсутніх полів.
        if not fields:
            continue
        mac = "невідомий"
        # MAC-адресу беремо з поля після lladdr, якщо воно є в записі.
        if "lladdr" in fields:
            index = fields.index("lladdr")
            if index + 1 < len(fields):
                mac = fields[index + 1]
        # Додаємо запис у список: перше поле — IP, останнє — стан сусіда.
        neighbors.append((fields[0], mac, fields[-1]))
    return neighbors


def ping_host(host):
    # Параметри ping: -4 — IPv4, -n — без визначення імен,
    # -c 1 — один запит, -W 2 — очікування відповіді до 2 секунд.
    # timeout=5 обмежує загальний час виконання процесу ping.
    # Надсилаємо один ICMP-запит і чекаємо відповіді не довше 2 секунд.
    result = subprocess.run(
        ["ping", "-4", "-n", "-c", "1", "-W", "2", host],
        capture_output=True, text=True, timeout=5,
    )
    # За кодом завершення ping визначаємо, чи отримано відповідь.
    if result.returncode == 0:
        print(f"[ОК] {host}: відповідь на ping отримано")
        return True
    print(f"[ПОМИЛКА] {host}: відповіді на ping немає або ping не виконано")
    # При невдалій перевірці показуємо вивід ping або повідомлення про помилку.
    print(result.stdout.strip() or result.stderr.strip())
    return False


def check_tcp_port(host, port):
    # Встановлюємо TCP-з'єднання і закриваємо його після перевірки.
    try:
        # Передаємо адресу й порт; with автоматично закриває створений сокет.
        with socket.create_connection((host, port), timeout=2):
            print(f"[ОК] {host}:{port}: TCP-з'єднання встановлено")
        return True
    except OSError as error:
        # Виводимо причину невдалого підключення та повертаємо False.
        print(f"[ПОМИЛКА] {host}:{port}: {error}")
        return False


def ipv4_address(value):
    # Перевіряємо текст аргументу як IPv4-адресу й повертаємо адресу рядком.
    try:
        return str(ipaddress.IPv4Address(value))
    except ipaddress.AddressValueError:
        # Передаємо argparse помилку, щоб він показав її разом із довідкою запуску.
        raise argparse.ArgumentTypeError("Вкажіть IPv4-адресу, наприклад 192.168.1.50")


def main():
    # Описуємо аргументи запуску: обов'язкову адресу та список TCP-портів.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, type=ipv4_address,
                        help="IPv4-адреса пристрою для перевірки")
    parser.add_argument("--ports", nargs="+", type=int, default=[22, 8000],
                        help="TCP-порти, які повинні бути доступні (типово: 22 8000)")
    # Зчитуємо аргументи: args.host містить адресу, args.ports — список чисел.
    args = parser.parse_args()
    # Відхиляємо номери портів поза допустимим діапазоном.
    if any(port < 1 or port > 65535 for port in args.ports):
        parser.error("Номер TCP-порту має бути в межах 1–65535")

    try:
        # Виводимо мережеві налаштування плати; маршрути також зберігаємо для пошуку шлюзу.
        show_command("ІНТЕРФЕЙСИ, IP І MAC", ["ip", "addr", "show"])
        routes = show_command("ШЛЮЗ ЗА ЗАМОВЧУВАННЯМ", ["ip", "-4", "route", "show", "default"])
        # Показуємо порти очікування підключень і вже встановлені TCP-з'єднання.
        show_command("ЛОКАЛЬНІ TCP/UDP-ПОРТИ", ["ss", "-tuln"])
        show_command("ВСТАНОВЛЕНІ TCP-З'ЄДНАННЯ", ["ss", "-tn", "state", "established"])
        # Показуємо сеанси користувачів і доступну інформацію про мережеві процеси.
        show_command("АКТИВНІ СЕСІЇ", ["w"])
        show_command("ПОРТИ ТА ПРОЦЕСИ", ["ss", "-tulpn"])
        print("Для перегляду процесів інших користувачів: sudo ss -tulpn")

        print("\n=== PING ШЛЮЗУ ===")
        # Отримуємо адресу шлюзу та перевіряємо її через ping, якщо адресу знайдено.
        gateway = find_gateway(routes)
        gateway_ok = False
        if gateway is None:
            print("[ПОМИЛКА] IPv4-шлюз за замовчуванням не знайдено")
        else:
            gateway_ok = ping_host(gateway)

        neighbors_output = show_command("ТАБЛИЦЯ СУСІДІВ", ["ip", "-4", "neigh"])
        print("\n=== ПЕРЕВІРКА СУСІДІВ ІЗ ARP-КЕШУ ===")
        # Розбираємо таблицю сусідів і послідовно перевіряємо отримані адреси.
        for host, mac, state in parse_neighbors(neighbors_output):
            print(f"IP={host}, MAC={mac}, стан={state}")
            if state in ("FAILED", "INCOMPLETE"):
                # Пропускаємо записи, для яких не вдалося визначити або підтвердити сусіда.
                print("[ПРОПУСК] Немає підтвердженої MAC-адреси сусіда")
            elif host != gateway and host != args.host:
                # Не повторюємо тут перевірку шлюзу та цілі: для них є окремі виклики.
                # Ці перевірки довідкові: сторонній сусід може блокувати ICMP.
                ping_host(host)

        print(f"\n=== ПЕРЕВІРКА ЦІЛІ {args.host} ===")
        # Зберігаємо результат ping цілі й перевіряємо всі порти зі списку аргументів.
        host_ok = ping_host(args.host)
        ports_ok = True
        for port in args.ports:
            # Перевіряємо TCP навіть тоді, коли пристрій не відповідає на ping.
            if not check_tcp_port(args.host, port):
                # Запам'ятовуємо невдале підключення, але продовжуємо перевіряти решту портів.
                ports_ok = False

        # Загальний успіх вимагає відповіді шлюзу й цілі та доступності всіх заданих портів.
        # Результати ping інших сусідів до цього підсумку не входять.
        success = gateway_ok and host_ok and ports_ok
        print("\n[РЕЗУЛЬТАТ] Обов'язкові перевірки пройдено" if success
              else "\n[РЕЗУЛЬТАТ] Є помилки обов'язкових перевірок")
        # Повертаємо 0 за успіху або 1 за невдалої обов'язкової перевірки.
        return 0 if success else 1
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        # Обробляємо помилки запуску команд, їх виконання та перевищення часу очікування.
        print(f"[ПОМИЛКА ВИКОНАННЯ] {error}")
        return 2


if __name__ == "__main__":
    # Запускаємо main лише при прямому запуску файла й передаємо її код завершення оболонці.
    raise SystemExit(main())
