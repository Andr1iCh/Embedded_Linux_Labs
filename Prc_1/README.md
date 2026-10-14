# Моніторинг ресурсів Raspberry Pi 5

## Що зроблено

Скрипт `sys_monitor.py` кожні 5 с записує в `telemetry.csv` час, температуру CPU, завантаження CPU та використання RAM. Якщо температура перевищує 60 °C, вмикає LED. Служба `monitor.service` запускає скрипт автоматично після ввімкнення плати.

## Принцип роботи

Температура читається з `/sys/class/thermal/thermal_zone0/temp`, CPU — з двох знімків `/proc/stat`, RAM — з `MemTotal` і `MemAvailable` у `/proc/meminfo`. GPIO керується через `gpiod`. Під час зупинки скрипт вимикає LED і звільняє GPIO.

## Запуск на платі

LED: GPIO18 (контакт 11) → резистор 330 Ом → анод; катод → GND (контакт 9). 

```bash
cd /home/arpi/sys_monitor
sudo apt install python3-venv python3-dev gpiod
python3 -m venv .venv
.venv/bin/python -m pip install 'gpiod>=2,<3'
gpioinfo
```

У `monitor.service` встановлюються шляхи `/home/arpi/sys_monitor/...` і `--chip /dev/gpiochipN` за виводом `gpioinfo`. Потім:

```bash
sudo cp monitor.service /etc/systemd/system/monitor.service
sudo systemctl daemon-reload
sudo systemctl enable --now monitor.service
```

## Результати

**Автозапуск після перезавантаження:**

```bash
systemctl is-enabled monitor.service
systemctl status monitor.service --no-pager
```

<img width="1447" height="337" alt="image" src="https://github.com/user-attachments/assets/7a368fc9-95e0-42e7-9cd7-b93d657ab98a" />


**Телеметрія** :

```bash
wc -l /home/arpi/sys_monitor/telemetry.csv
tail -n 21 /home/arpi/sys_monitor/telemetry.csv
```

<img width="729" height="430" alt="image" src="https://github.com/user-attachments/assets/cf82ac39-720c-437e-8e7e-f716440f876d" />


**GPIO та LED:**

```bash
gpioinfo | grep -E 'gpiochip|sys-monitor'
```
<img width="943" height="169" alt="image" src="https://github.com/user-attachments/assets/6e55dd82-f31f-4970-97fe-ff136a4db257" />

<img width="2560" height="1436" alt="image" src="https://github.com/user-attachments/assets/c1d9b16f-b9e0-4099-9323-eb75118da325" />
