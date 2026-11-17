#!/usr/bin/env python3
"""Веб-панель керування частотою та передавання імітованого спектра."""

import asyncio
import math
import random
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field


app = FastAPI(title="SDR Web Monitor")

# Зберігаємо одну поточну частоту для всіх підключених клієнтів.
# Після перезапуску програми відновлюється початкове значення 100.5 МГц.
sdr_state = {"frequency_mhz": 100.5}
BASE_DIR = Path(__file__).resolve().parent
POINT_COUNT = 128
SPAN_MHZ = 2.0
SIGNAL_MHZ = 100.5


class FrequencyCommand(BaseModel):
    # Перевіряємо поле JSON: скінченне число від 1 до 2000 МГц.
    # Це межі навчального інтерфейсу, а не характеристика реального приймача.
    frequency_mhz: float = Field(ge=1, le=2000, allow_inf_nan=False)


def generate_spectrum(center_mhz):
    # Створюємо список амплітуд для рівномірно розташованих частотних точок.
    # Імітований сигнал має фіксовану частоту 100.5 МГц, ширина огляду — 2 МГц.
    spectrum = []
    for index in range(POINT_COUNT):
        frequency = center_mhz - SPAN_MHZ / 2 + index * SPAN_MHZ / (POINT_COUNT - 1)
        # Додаємо випадковий фон і пік, висота якого зменшується з відстанню до сигналу.
        noise = random.uniform(5, 15)
        peak = 70 * math.exp(-((frequency - SIGNAL_MHZ) / 0.06) ** 2)
        spectrum.append(round(noise + peak, 2))
    return spectrum


@app.get("/")
async def get_ui():
    # Віддаємо index.html із каталогу програми незалежно від поточного каталогу запуску.
    return FileResponse(BASE_DIR / "index.html", media_type="text/html")


@app.post("/api/frequency")
async def change_frequency(command: FrequencyCommand):
    # Зберігаємо перевірену частоту; наступні кадри спектра використовуватимуть її.
    # У цій роботі драйвер SDR не викликається: дані генеруються програмно.
    sdr_state["frequency_mhz"] = command.frequency_mhz
    print(f"[КЕРУВАННЯ] Частоту змінено на {command.frequency_mhz} МГц", flush=True)
    return {"status": "ok", "frequency_mhz": command.frequency_mhz}


@app.websocket("/ws/spectrum")
async def spectrum_stream(websocket: WebSocket):
    # Приймаємо запит браузера на встановлення WebSocket-з'єднання.
    await websocket.accept()
    try:
        while True:
            # Зчитуємо поточну частоту й надсилаємо її разом із масивом амплітуд.
            frequency = sdr_state["frequency_mhz"]
            await websocket.send_json({
                "mode": "simulation",
                "frequency_mhz": frequency,
                "span_mhz": SPAN_MHZ,
                "fft_data": generate_spectrum(frequency),
            })
            # Призупиняємо цю корутину на 0.1 с, дозволяючи обробляти інші запити.
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        # Завершуємо цикл цього клієнта після закриття вкладки або втрати з'єднання.
        print("[МЕРЕЖА] Клієнт відключився від потоку спектра", flush=True)


if __name__ == "__main__":
    # Запускаємо один сервер на всіх IPv4-інтерфейсах плати, TCP-порт 8001.
    uvicorn.run(app, host="0.0.0.0", port=8001)
