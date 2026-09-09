import asyncio
import json
import sqlite3
import threading
import time
from contextlib import asynccontextmanager
from queue import Empty, Queue
from typing import List

import serial
import serial.tools.list_ports
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

DB_FILE = "sensor_data.db"
BAUD_RATE = 115200
SIMULATE = False

MODES = ["Papel", "Textiles", "Metal"]

current_mode_index = 0
clients: List[WebSocket] = []

global_ser = None
serial_thread = None
serial_stop_event = threading.Event()

serial_queue = Queue()
command_queue = Queue()


# ------------------------------------------------------------
# BASE DE DATOS
# ------------------------------------------------------------

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            raw_data TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_reading(data):
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute(
            "INSERT INTO readings(timestamp, raw_data) VALUES(?, ?)",
            (time.time(), data)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"ERROR DB -> {e}")


init_db()


# ------------------------------------------------------------
# MODOS
# ------------------------------------------------------------

def get_mode():
    return MODES[current_mode_index]


def set_mode(index):
    global current_mode_index

    try:
        index = int(index)
    except (ValueError, TypeError):
        index = 0

    current_mode_index = index % len(MODES)
    return get_mode()


def next_mode():
    global current_mode_index
    current_mode_index = (current_mode_index + 1) % len(MODES)
    return get_mode()


# ------------------------------------------------------------
# WEBSOCKET
# ------------------------------------------------------------

async def broadcast(data):
    if not clients:
        return

    disconnected = []

    for client in list(clients):
        try:
            await client.send_text(data)
        except Exception as e:
            print(f"ERROR WS -> {e}")
            disconnected.append(client)

    for client in disconnected:
        if client in clients:
            clients.remove(client)


async def broadcast_mode():
    await broadcast(json.dumps({
        "type": "mode",
        "mode_index": current_mode_index,
        "mode": get_mode()
    }))


# ------------------------------------------------------------
# MICRO:BIT
# ------------------------------------------------------------

def auto_detect_microbit():
    ports = serial.tools.list_ports.comports()

    for port in ports:
        desc = (port.description or "").lower()

        if (
            "mbed" in desc
            or "micro:bit" in desc
            or port.vid == 0x0D28
        ):
            return port.device

    return None


# ------------------------------------------------------------
# COMANDOS SERIAL
# ------------------------------------------------------------

def send_serial_command(command):
    if SIMULATE:
        return True

    command_queue.put(command)
    print(f"TX ENCOLADO -> {command}")
    return True


# ------------------------------------------------------------
# PROCESAMIENTO DE DATOS
# ------------------------------------------------------------

def handle_serial_line(line):
    global current_mode_index

    line = line.strip()

    if not line:
        return

    print(f"RX SERIAL -> {line}")

    try:
        data = json.loads(line)

        if not isinstance(data, dict):
            return

        if data.get("type") == "mode":
            set_mode(data.get("mode_index", 0))

            serial_queue.put(json.dumps({
                "type": "mode",
                "mode_index": current_mode_index,
                "mode": get_mode()
            }))

            return

        if any(
            key in data
            for key in ("temperature", "humidity", "light")
        ):
            if "mode_index" in data:
                set_mode(data["mode_index"])

            save_reading(line)
            serial_queue.put(line)
            return

    except json.JSONDecodeError:
        pass

    except Exception as e:
        print(f"ERROR PROCESANDO JSON -> {e}")

    upper = line.upper()

    if upper.startswith("MODO:") or upper.startswith("MODE:"):
        try:
            index = int(line.split(":", 1)[1].strip())
            set_mode(index)

            serial_queue.put(json.dumps({
                "type": "mode",
                "mode_index": current_mode_index,
                "mode": get_mode()
            }))

        except ValueError:
            print(f"ERROR MODO -> {line}")

        return

    save_reading(line)
    serial_queue.put(line)


# ------------------------------------------------------------
# HILO SERIAL
# ------------------------------------------------------------

def serial_reader_thread():
    global global_ser

    print("HILO SERIAL INICIADO")

    while not serial_stop_event.is_set():
        port = auto_detect_microbit()

        if not port:
            print("Buscando Micro:bit...")
            serial_stop_event.wait(2)
            continue

        try:
            print(f"Conectando a micro:bit en {port}...")

            ser = serial.Serial(
                port=port,
                baudrate=BAUD_RATE,
                timeout=0.2,
                write_timeout=1
            )

            global_ser = ser

            print("¡Micro:bit conectada!")

            time.sleep(0.5)

            # El hilo serial es el UNICO que escribe en COM4.
            command_queue.put(
                f"MODO:{current_mode_index}"
            )

            while (
                ser.is_open
                and not serial_stop_event.is_set()
            ):
                # --------------------------------------------
                # ESCRITURA
                # --------------------------------------------

                while True:
                    try:
                        command = command_queue.get_nowait()
                    except Empty:
                        break

                    try:
                        ser.write(
                            (command + "\n").encode("utf-8")
                        )
                        ser.flush()
                        print(f"TX SERIAL -> {command}")

                    except serial.SerialException as e:
                        print(f"ERROR TX SERIAL -> {e}")
                        raise

                # --------------------------------------------
                # LECTURA
                # --------------------------------------------

                try:
                    line = ser.readline()

                    if line:
                        text = line.decode(
                            "utf-8",
                            errors="ignore"
                        ).strip()

                        if text:
                            handle_serial_line(text)

                except serial.SerialException as e:
                    print(f"ERROR RX SERIAL -> {e}")
                    break

        except serial.SerialException as e:
            print(f"ERROR SERIAL -> {e}")

        except Exception as e:
            print(f"ERROR HILO SERIAL -> {e}")

        finally:
            try:
                if global_ser and global_ser.is_open:
                    global_ser.close()
            except Exception:
                pass

            global_ser = None

            print("Puerto serial cerrado.")

        if not serial_stop_event.is_set():
            print("Reintentando conexión en 2 segundos...")
            serial_stop_event.wait(2)

    print("HILO SERIAL DETENIDO")


# ------------------------------------------------------------
# COLA SERIAL -> WEBSOCKET
# ------------------------------------------------------------

async def serial_queue_processor():
    print("PROCESADOR DE COLA INICIADO")

    while True:
        try:
            data = serial_queue.get_nowait()
        except Empty:
            await asyncio.sleep(0.01)
            continue

        try:
            print(f"WS OUT -> {data}")
            await broadcast(data)
        except Exception as e:
            print(f"ERROR WS OUT -> {e}")


# ------------------------------------------------------------
# ENDPOINTS
# ------------------------------------------------------------

@app.get("/data")
def get_historical_data(limit: int = 100):
    conn = sqlite3.connect(DB_FILE)

    rows = conn.execute(
        """
        SELECT timestamp, raw_data
        FROM readings
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,)
    ).fetchall()

    conn.close()

    return [
        {"timestamp": timestamp, "data": data}
        for timestamp, data in rows
    ]


@app.get("/mode")
def get_mode_endpoint():
    return {
        "mode_index": current_mode_index,
        "mode": get_mode()
    }


# ------------------------------------------------------------
# WEBSOCKET
# ------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    clients.append(websocket)

    print(
        f"WS CONECTADO -> clientes: {len(clients)}"
    )

    await websocket.send_text(json.dumps({
        "type": "mode",
        "mode_index": current_mode_index,
        "mode": get_mode()
    }))

    try:
        while True:
            message = await websocket.receive_text()

            print(f"WS IN -> {message}")

            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                continue

            command = data.get("command")

            if not command:
                continue

            if command == "cambiar_modo":
                mode = next_mode()

                print(
                    f"MODO WEB -> "
                    f"{current_mode_index} ({mode})"
                )

                send_serial_command(
                    f"MODO:{current_mode_index}"
                )

                await broadcast_mode()
                continue

            if command.startswith("modo:"):
                try:
                    index = int(
                        command.split(":", 1)[1]
                    )

                    mode = set_mode(index)

                    print(
                        f"MODO WEB -> "
                        f"{current_mode_index} ({mode})"
                    )

                    send_serial_command(
                        f"MODO:{current_mode_index}"
                    )

                    await broadcast_mode()

                except ValueError:
                    print(
                        f"COMANDO DE MODO INVALIDO -> {command}"
                    )

                continue

            if command in {
                "incendio",
                "inundacion",
                "humedad",
                "uv",
                "luz",
                "optimo"
            }:
                send_serial_command(command)

    except WebSocketDisconnect:
        print("WS DESCONECTADO")

    except Exception as e:
        print(f"ERROR WS -> {e}")

    finally:
        if websocket in clients:
            clients.remove(websocket)

        print(
            f"WS CLIENTES -> {len(clients)}"
        )


# ------------------------------------------------------------
# SIMULACION
# ------------------------------------------------------------

async def realtime_broadcaster():
    if not SIMULATE:
        await asyncio.Event().wait()
        return

    import random

    while True:
        data = json.dumps({
            "temperature": round(
                random.uniform(20, 35), 2
            ),
            "humidity": round(
                random.uniform(35, 75), 2
            ),
            "light": random.randint(0, 800),
            "mode_index": current_mode_index,
            "mode": get_mode(),
            "simulated": True
        })

        save_reading(data)
        serial_queue.put(data)

        await asyncio.sleep(1)


# ------------------------------------------------------------
# LIFESPAN
# ------------------------------------------------------------

@asynccontextmanager
async def lifespan(app):
    global serial_thread

    serial_stop_event.clear()

    serial_thread = threading.Thread(
        target=serial_reader_thread,
        daemon=True
    )

    serial_thread.start()

    queue_task = asyncio.create_task(
        serial_queue_processor()
    )

    simulation_task = asyncio.create_task(
        realtime_broadcaster()
    )

    print("BACKEND COMPLETAMENTE INICIADO")

    try:
        yield

    finally:
        print("DETENIENDO BACKEND...")

        serial_stop_event.set()

        queue_task.cancel()
        simulation_task.cancel()

        if global_ser:
            try:
                if global_ser.is_open:
                    global_ser.close()
            except Exception:
                pass


app.router.lifespan_context = lifespan


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000
    )