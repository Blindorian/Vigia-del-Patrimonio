import asyncio
import serial
import sqlite3
import json
import time
import threading
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de Base de Datos
DB_FILE = "sensor_data.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            raw_data TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Configuración Serial
SERIAL_PORT = "COM4"  # Cambiar al puerto correcto
BAUD_RATE = 115200
SIMULATE = False  # Cambiar a False si tienes la micro:bit conectada

clients: List[WebSocket] = []

def save_reading(data: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO readings (timestamp, raw_data) VALUES (?, ?)", (time.time(), data))
    conn.commit()
    conn.close()

async def broadcast(data: str):
    for client in clients:
        try:
            await client.send_text(data)
        except:
            pass

import serial.tools.list_ports

def auto_detect_microbit():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        desc = port.description.lower()
        if "mbed" in desc or "micro:bit" in desc or port.vid == 0x0D28:
            return port.device
    # Si no lo reconoce por nombre o VID, puedes intentar forzar COM6 u otro, pero mejor retornar None
    return None

global_ser = None
app_loop = None

def serial_reader_thread():
    global global_ser
    if not SIMULATE:
        while True:
            port = auto_detect_microbit()
            if port:
                try:
                    print(f"Conectando a micro:bit en {port}...")
                    # Añadimos dtr=False para evitar problemas de permisos de Windows (Error 13)
                    global_ser = serial.Serial()
                    global_ser.port = port
                    global_ser.baudrate = BAUD_RATE
                    global_ser.timeout = 1
                    global_ser.setDTR(False)
                    global_ser.open()
                    
                    print("¡Micro:bit conectado exitosamente!")
                    while True:
                        line = global_ser.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            save_reading(line)
                            # Enviar el dato por WebSockets a la web
                            if app_loop and app_loop.is_running():
                                asyncio.run_coroutine_threadsafe(broadcast(line), app_loop)
                except Exception as e:
                    print(f"Error Serial: {e}")
                    if global_ser and global_ser.is_open:
                        global_ser.close()
            else:
                print("Buscando Micro:bit... Asegúrate de que no esté abierto en MakeCode.")
            time.sleep(3)

# Iniciar hilo de lectura serial
t = threading.Thread(target=serial_reader_thread, daemon=True)
t.start()

# API Endpoints
@app.get("/data")
def get_historical_data(limit: int = 100):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT timestamp, raw_data FROM readings ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [{"timestamp": r[0], "data": r[1]} for r in rows]

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.append(websocket)
    try:
        while True:
            # El websocket recibe comandos desde la web
            data = await websocket.receive_text()
            try:
                cmd_data = json.loads(data)
                if "command" in cmd_data:
                    command = cmd_data["command"]
                    # Si el puerto serial está abierto, enviamos el comando al micro:bit
                    if not SIMULATE and global_ser and global_ser.is_open:
                        try:
                            global_ser.write(f"{command}\n".encode('utf-8'))
                            global_ser.flush()
                            # Limpiamos el buffer de entrada para evitar leer un "echo"
                            global_ser.reset_input_buffer()
                        except Exception as e:
                            print(f"Error escribiendo al serial: {e}")
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        clients.remove(websocket)

# Tarea asíncrona para simular y enviar datos por WS
async def realtime_broadcaster():
    if SIMULATE:
        import random
        while True:
            # Puedes modificar los rangos según los escenarios a simular
            data = {
                "temperature": round(random.uniform(20.0, 35.0), 2), 
                "light": random.randint(0, 255), 
                "simulated": True
            }
            data_str = json.dumps(data)
            save_reading(data_str) # Guardamos en la base de datos
            await broadcast(data_str) # Enviamos a los clientes web
            await asyncio.sleep(1)
    else:
        # En modo real ya se hace el broadcast desde el hilo de lectura serial
        pass

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    global app_loop
    app_loop = asyncio.get_running_loop()
    # Iniciar tareas en background al arrancar
    task = asyncio.create_task(realtime_broadcaster())
    yield
    # Limpiar si es necesario al cerrar
    task.cancel()

app.router.lifespan_context = lifespan

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
