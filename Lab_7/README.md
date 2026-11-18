# Лабораторна робота 7. Зберігання телеметрії SDR у SQLite та сповіщення через модуль ядра Linux

## Мета роботи

Зберегти історію частот і рівнів сигналів у SQLite. Реалізувати модуль ядра Linux, який приймає команду через символьний пристрій і записує тривогу в журнал ядра.

## Опис системи та реалізація

Скрипт `db_kernel_logger.py` додає до таблиці `signals` час, частоту в МГц і RSSI в dBm. Якщо RSSI перевищує −20 dBm, скрипт записує байт `1` у `/dev/sdr_alert`. Модуль `sdr_alert_mod` обробляє запис і викликає `pr_alert()`. Результат перевіряється через SQLite і `dmesg`.

## Підключення та обладнання

Комп'ютер із WSL і Raspberry Pi 5 підключені до локальної мережі. Плату використовуємо для збирання модуля, запуску скрипта та перевірки журналу. Частоти й RSSI задані в коді для імітації вимірювань. Достатньо Raspberry Pi та SSH-з'єднання.

## Виконання та перевірка

**1. Підготовка**

Встановлюємо компілятор і make через пакет `build-essential`, Python, клієнт SQLite та заголовки саме запущеного ядра:

```bash
cd ~/Lab_7
sudo apt update
sudo apt install build-essential python3 sqlite3 "linux-headers-$(uname -r)"
```

Перевіряємо версію запущеного ядра й шлях до його заголовків. Якщо `apt` не знайшов пакет заголовків, зупиняємося на цьому кроці та перевіряємо, які пакети доступні для версії з `uname -r`:

```bash
uname -r
ls -ld "/lib/modules/$(uname -r)/build"
```

![alt text](assets/image.png)

**2. Збирання модуля**

Команда `make` передає вихідний файл системі збирання поточного ядра. Після збирання перевіряємо наявність файла `sdr_alert_mod.ko`:

```bash
make
ls -l sdr_alert_mod.ko
```

![alt text](assets/image-1.png)

**3. Завантаження модуля**

Завантажуємо зібраний модуль у поточне ядро. Він реєструє пристрій, після чого Raspberry Pi OS створює вузол `/dev/sdr_alert`:

```bash
sudo insmod ./sdr_alert_mod.ko
sudo udevadm settle
```

Передаємо вузол поточному користувачу, щоб запускати Python без sudo. Команда `lsmod` показує завантажений модуль, а літера `c` на початку прав у `ls -l` позначає символьний пристрій:

```bash
sudo chown "$(id -u):$(id -g)" /dev/sdr_alert
lsmod | grep '^sdr_alert_mod'
ls -l /dev/sdr_alert
```

![alt text](assets/image-2.png)

**4. Запис сигналів і перевірка тривоги**

Запускаємо програму. Вона додає два тестові вимірювання до бази та передає команду тривоги лише для сигналу −12,5 dBm:

```bash
python3 db_kernel_logger.py
```

![alt text](assets/image-3.png)

Переглядаємо останні два записи з таблиці `signals`. Повторний запуск програми додає ще два рядки:

```bash
sqlite3 -header -column sdr_telemetry.db \
  'SELECT id, frequency_mhz, rssi_dbm FROM signals ORDER BY id DESC LIMIT 2;'
```

![alt text](assets/image-4.png)

Переглядаємо кольоровий вивід журналу ядра. Після рядка про реєстрацію пристрою шукаємо повідомлення `[SDR KERNEL ALERT] Critical Signal Level Detected!`:

```bash
sudo dmesg --color=always | grep -E 'Registered /dev/sdr_alert|Critical Signal Level Detected!' | tail -n 5
```

![alt text](assets/image-5.png)

## Висновок

Підготовлено запис тестової телеметрії у SQLite та передавання тривоги до модуля ядра. Результати перевіряються за двома рядками в таблиці `signals` і повідомленням про перевищення порогу в журналі ядра.
