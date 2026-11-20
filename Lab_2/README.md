# Лабораторна робота №2 — Керування USB-пристроями та правила udev

**Студент:** Чухлєб Андрій, РЕ-31

**Тема:** Керування USB-пристроями та створення правил udev для апаратури радіомоніторингу в Linux.

## Мета роботи

Опанувати ідентифікацію USB-пристроїв, створення постійних імен і налаштування прав доступу через udev. Перевірити готовність USB-UART адаптера до роботи за допомогою Python.

## Структура репозиторію

| Файл або каталог | Призначення |
| --- | --- |
| [`99-radio-monitor.rules`](99-radio-monitor.rules) | Шаблон правил udev для посилань `/dev/uart_compass` і `/dev/sdr_primary`. Правило для підключеного адаптера генерується на платі. |
| [`generate_rules.py`](generate_rules.py) | Формує правило udev за ідентифікаторами підключеного USB-UART адаптера. |
| [`check_hardware.py`](check_hardware.py) | Перевіряє доступ до пристроїв і виконує loopback-тест USB-UART. |
| [`blacklist-sdr.conf`](blacklist-sdr.conf) | Конфігурація modprobe для блокування драйвера DVB для RTL-SDR. |
| [`README.md`](README.md) | Опис лабораторної, команди розгортання й результати перевірки. |

## Опис системи та реалізація

Система складається з Raspberry Pi 5 і USB-UART адаптера PL2303. Скрипт `generate_rules.py` визначає VID/PID адаптера та формує правило `99-radio-monitor.rules`. Правило додає постійне ім'я `/dev/uart_compass` і права `0666` для роботи без sudo. Прив'язка виконується за серійним номером, а за його відсутності — за USB-портом.

Скрипт `check_hardware.py` перевіряє посилання, права доступу й передачу байтів у режимі loopback: передані через TX дані повертаються через RX. SDR-приймач відсутній, тому його перевірка пропускається через `--skip-sdr`; файл `blacklist-sdr.conf` не встановлюється.

## Підключення

PL2303 підключено до USB-порту Raspberry Pi. TX і RX самого адаптера з'єднано між собою. GPIO Raspberry Pi не використовуються. Перемичка вибору напруги залишається в положенні 3.3 V, для TX–RX використовується окрема перемичка.

<img alt="image-1" src="https://github.com/user-attachments/assets/512005b2-b460-4642-889c-6097a23153e9" />

## Виконання та перевірка

**1. Підготовка й ідентифікація адаптера**

Усі команди виконуємо на Raspberry Pi. Переходимо до папки лабораторної та встановлюємо залежності:

```bash
cd ~/Lab_2
sudo apt update
sudo apt install python3-serial usbutils
```

Переглядаємо підключені USB-пристрої та знаходимо PL2303:

```bash
lsusb
```
<img width="950" height="139" alt="image-2" src="https://github.com/user-attachments/assets/95d7e765-acf8-4667-a952-ab89f4a2cb0d" />

Перевіряємо ім'я USB-UART порту та переглядаємо ідентифікатори адаптера:

```bash
ls -l /dev/ttyUSB*
udevadm info -a -n /dev/ttyUSB0 | grep -E 'idVendor|idProduct|serial'
```
<img width="1118" height="242" alt="image-3" src="https://github.com/user-attachments/assets/219219ff-e3b4-42a5-9843-ca70b1429187" />

**2. Створення та застосування правила udev**

Створюємо правило за ідентифікаторами підключеного адаптера та переглядаємо вміст файла:

```bash
python3 generate_rules.py /dev/ttyUSB0
cat 99-radio-monitor.rules
```
<img width="1049" height="213" alt="image" src="https://github.com/user-attachments/assets/ae44204e-1916-48b6-b81d-5b5ddd4df884" />

Копіюємо файл у системний каталог правил udev:

```bash
sudo install -m 644 99-radio-monitor.rules /etc/udev/rules.d/99-radio-monitor.rules
```

Даємо службі udev команду перечитати файли правил:

```bash
sudo udevadm control --reload-rules
```

Повторно створюємо події додавання для наявних пристроїв підсистеми tty. Udev обробляє їх за оновленими правилами, тому для відповідного адаптера створюється посилання та встановлюються права без фізичного перепідключення USB:

```bash
sudo udevadm trigger --action=add --subsystem-match=tty
```

Чекаємо, поки udev завершить обробку поточної черги подій:

```bash
sudo udevadm settle
```

Перевіряємо створене посилання та права пристрою, на який воно вказує:

```bash
ls -l /dev/uart_compass
stat -L -c '%a %n' /dev/uart_compass
```
<img width="799" height="96" alt="image-4" src="https://github.com/user-attachments/assets/bce9d1c2-1127-4cfa-a12b-02513cbd375b" />

**3. Перевірка передачі даних без sudo**

Запускаємо loopback-тест без sudo та перевіряємо код завершення:

```bash
python3 check_hardware.py --loopback --skip-sdr
echo $?
```
<img width="846" height="192" alt="image-5" src="https://github.com/user-attachments/assets/48876315-6628-41d9-bb44-68372d8d67c7" />

**4. Перевірка після перепідключення**

Від'єднуємо PL2303 від USB та підключаємо до того самого USB-порту. Очікуємо завершення обробки подій udev і перевіряємо, чи посилання створилося повторно:

```bash
sudo udevadm settle
ls -l /dev/uart_compass
```
<img width="802" height="48" alt="image-6" src="https://github.com/user-attachments/assets/047d3be7-6ce5-42e4-a5e1-1d95ec92be41" />

Повторно перевіряємо передачу байтів без перевстановлення правила:

```bash
python3 check_hardware.py --loopback --skip-sdr
echo $?
```
<img width="868" height="187" alt="image-7" src="https://github.com/user-attachments/assets/3c7dc169-600b-41da-bd67-d5ac84758222" />

## Висновок

Створено правило udev для PL2303, яке надає адаптеру постійне ім’я `/dev/uart_compass`. Перевірено появу посилання після перепідключення й передачу даних у режимі loopback без sudo. Апаратна перевірка охопила USB-UART адаптер.
