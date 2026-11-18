#!/usr/bin/env bash
# Запускати у WSL: bash Lab_5/ssh_tunnel.sh [користувач@адреса_RPi].
set -eu

# Використовуємо передану адресу або адресу плати з попередньої лабораторної.
target="${1:-arpi@192.168.0.150}"
key="$HOME/.ssh/id_ed25519_lab5"

# Перевіряємо наявність приватного ключа до запуску SSH.
if [ ! -f "$key" ]; then
    echo "Не знайдено ключ: $key. Спочатку виконайте пункт створення ключа в README." >&2
    exit 1
fi

echo "Тунель до $target: http://127.0.0.1:8888 -> RPi:127.0.0.1:8001"
echo "Цей термінал залиште відкритим. Для зупинки тунелю натисніть Ctrl+C."

# Відкриваємо порт лише на loopback клієнта та передаємо з'єднання через SSH.
# -N не запускає віддалену команду; ExitOnForwardFailure виявляє помилку відкриття порту.
# ServerAliveInterval/CountMax завершують SSH після втрати зв'язку із сервером.
exec ssh -i "$key" -o IdentitiesOnly=yes \
    -o ExitOnForwardFailure=yes \
    -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
    -L 127.0.0.1:8888:127.0.0.1:8001 -N "$target"
