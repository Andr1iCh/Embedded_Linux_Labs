#!/usr/bin/env python3
"""Створення двох WireGuard-конфігурацій із новими ключами на Raspberry Pi."""

import argparse
import ipaddress
import os
import subprocess
from pathlib import Path


def create_keys():
    # Генеруємо приватний ключ і передаємо його через stdin команді отримання відкритого ключа.
    private = subprocess.run(
        ["wg", "genkey"], capture_output=True, text=True, check=True, timeout=5,
    ).stdout.strip()
    public = subprocess.run(
        ["wg", "pubkey"], input=private + "\n", capture_output=True,
        text=True, check=True, timeout=5,
    ).stdout.strip()
    return private, public


def ipv4_address(value):
    # Перевіряємо адресу кінцевої точки перед вставленням у конфігурацію.
    try:
        return str(ipaddress.IPv4Address(value))
    except ipaddress.AddressValueError:
        raise argparse.ArgumentTypeError("Вкажіть IPv4-адресу Raspberry Pi або її зовнішнього шлюзу")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", type=ipv4_address, default="192.168.0.150",
                        help="досяжна IPv4-адреса RPi; UDP-порт 51820")
    parser.add_argument("--output", type=Path,
                        default=Path.home() / ".config" / "embedded-linux-lab5",
                        help="новий каталог для конфігурацій поза репозиторієм")
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    if output.exists():
        parser.error("Каталог уже існує. Використайте інший --output; наявні ключі не перезаписуються.")

    try:
        # Створюємо окремі пари ключів для сервера та клієнта.
        server_private, server_public = create_keys()
        client_private, client_public = create_keys()

        server_config = (
            "[Interface]\n"
            "Address = 10.77.0.1/24\n"
            "ListenPort = 51820\n"
            f"PrivateKey = {server_private}\n\n"
            "[Peer]\n"
            f"PublicKey = {client_public}\n"
            "AllowedIPs = 10.77.0.2/32\n"
        )
        client_config = (
            "[Interface]\n"
            "Address = 10.77.0.2/24\n"
            f"PrivateKey = {client_private}\n\n"
            "[Peer]\n"
            f"PublicKey = {server_public}\n"
            "AllowedIPs = 10.77.0.1/32\n"
            f"Endpoint = {args.endpoint}:51820\n"
            "PersistentKeepalive = 25\n"
        )

        # Забороняємо доступ інших користувачів до нових каталогів і файлів із ключами.
        os.umask(0o077)
        output.mkdir(parents=True, mode=0o700)
        for name, config in (("wg0.conf", server_config), ("wg-client.conf", client_config)):
            # Режим x створює новий файл і відхиляє перезапис наявного.
            with (output / name).open("x", encoding="utf-8", newline="\n") as file:
                file.write(config)
        # Виводимо лише шляхи; приватні ключі в термінал не потрапляють.
        print(f"Створено: {output / 'wg0.conf'}")
        print(f"Створено: {output / 'wg-client.conf'}")
        print("До Git додаються лише шаблони .example.")
        return 0
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        print("[ПОМИЛКА] Не вдалося створити конфігурації. Перевірте встановлення wireguard-tools і права каталогу.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
