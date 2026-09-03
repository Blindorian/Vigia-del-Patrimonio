import asyncio
import serial
import serial.tools.list_ports
import sqlite3
import json
import time
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI,WebSocket,WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List

app=FastAPI()
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])

DB_FILE="sensor_data.db"
SERIAL_PORT="COM4"
BAUD_RATE=115200
SIMULATE=False
MODES=["Papel","Textiles","Metal","Madera","Pinturas"]
current_mode_index=0
clients:List[WebSocket]=[]
global_ser=None
app_loop=None

def init_db():
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS readings (id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp REAL,raw_data TEXT)")
    conn.commit()
    conn.close()

init_db()

def get_mode():
    return MODES[current_mode_index]

def set_mode(index):
    global current_mode_index
    try:index=int(index)
    except:index=0
    current_mode_index=index%len(MODES)
    return get_mode()

def next_mode():
    global current_mode_index
    current_mode_index=(current_mode_index+1)%len(MODES)
    return get_mode()

def save_reading(data):
    try:
        conn=sqlite3.connect(DB_FILE)
        c=conn.cursor()
        c.execute("INSERT INTO readings(timestamp,raw_data) VALUES(?,?)",(time.time(),data))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error guardando lectura: {e}")

async def broadcast(data):
    disconnected=[]
    for client in clients:
        try:
            await client.send_text(data)
        except Exception:
            disconnected.append(client)
    for client in disconnected:
        if client in clients:
            clients.remove(client)

async def broadcast_mode():
    await broadcast(json.dumps({"type":"mode","mode_index":current_mode_index,"mode":get_mode()}))

def auto_detect_microbit():
    ports=serial.tools.list_ports.comports()
    for port in ports:
        desc=(port.description or "").lower()
        if "mbed" in desc or "micro:bit" in desc or port.vid==0x0D28:
            return port.device
    return None

def send_serial_command(command):
    global global_ser
    if SIMULATE:
        return True
    if global_ser and global_ser.is_open:
        try:
            global_ser.write((command+"\n").encode("utf-8"))
            global_ser.flush()
            print(f"TX -> {command}")
            return True
        except Exception as e:
            print(f"Error escribiendo al serial: {e}")
    return False

def handle_serial_line(line):
    global current_mode_index
    line=line.strip()
    if not line:return
    print(f"RX SERIAL -> {line}")
    try:
        data=json.loads(line)
        if isinstance(data,dict):
            if data.get("type")=="mode":
                set_mode(data.get("mode_index",0))
                if app_loop and app_loop.is_running():
                    asyncio.run_coroutine_threadsafe(broadcast_mode(),app_loop)
                return
            if "mode_index" in data:
                set_mode(data["mode_index"])
                if app_loop and app_loop.is_running():
                    asyncio.run_coroutine_threadsafe(broadcast_mode(),app_loop)
            save_reading(line)
            if app_loop and app_loop.is_running():
                asyncio.run_coroutine_threadsafe(broadcast(line),app_loop)
            return
    except json.JSONDecodeError:
        pass
    mode_text=line.upper()
    if mode_text.startswith("MODO:") or mode_text.startswith("MODE:"):
        try:
            index=int(line.split(":",1)[1].strip())
            set_mode(index)
            if app_loop and app_loop.is_running():
                asyncio.run_coroutine_threadsafe(broadcast_mode(),app_loop)
            return
        except ValueError:
            pass
    save_reading(line)
    if app_loop and app_loop.is_running():
        asyncio.run_coroutine_threadsafe(broadcast(line),app_loop)

def serial_reader_thread():
    global global_ser
    while not SIMULATE:
        port=auto_detect_microbit()
        if port:
            try:
                print(f"Conectando a micro:bit en {port}...")
                global_ser=serial.Serial(port=port,baudrate=BAUD_RATE,timeout=1)
                global_ser.setDTR(False)
                print("¡Micro:bit conectada!")
                send_serial_command(f"MODO:{current_mode_index}")
                while global_ser.is_open:
                    try:
                        line=global_ser.readline().decode("utf-8",errors="ignore").strip()
                        if line:
                            handle_serial_line(line)
                    except serial.SerialException:
                        break
            except Exception as e:
                print(f"Error Serial: {e}")
            finally:
                try:
                    if global_ser and global_ser.is_open:
                        global_ser.close()
                except Exception:
                    pass
                global_ser=None
        else:
            print("Buscando Micro:bit... Asegúrate de que esté conectada y que MakeCode no esté usando el puerto.")
        time.sleep(3)

threading.Thread(target=serial_reader_thread,daemon=True).start()

@app.get("/data")
def get_historical_data(limit:int=100):
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()
    c.execute("SELECT timestamp,raw_data FROM readings ORDER BY id DESC LIMIT ?",(limit,))
    rows=c.fetchall()
    conn.close()
    return [{"timestamp":r[0],"data":r[1]} for r in rows]

@app.get("/mode")
def get_mode_endpoint():
    return {"mode_index":current_mode_index,"mode":get_mode()}

@app.websocket("/ws")
async def websocket_endpoint(websocket:WebSocket):
    await websocket.accept()
    clients.append(websocket)
    await websocket.send_text(json.dumps({"type":"mode","mode_index":current_mode_index,"mode":get_mode()}))
    try:
        while True:
            data=await websocket.receive_text()
            try:
                cmd_data=json.loads(data)
            except json.JSONDecodeError:
                continue
            command=cmd_data.get("command")
            if not command:
                continue
            if command=="cambiar_modo":
                mode=next_mode()
                print(f"Modo cambiado desde WEB -> {current_mode_index} ({mode})")
                send_serial_command(f"MODO:{current_mode_index}")
                await broadcast_mode()
                continue
            if command.startswith("modo:"):
                try:
                    index=int(command.split(":",1)[1])
                    mode=set_mode(index)
                    print(f"Modo seleccionado -> {current_mode_index} ({mode})")
                    send_serial_command(f"MODO:{current_mode_index}")
                    await broadcast_mode()
                except ValueError:
                    pass
                continue
            if command in ["incendio","inundacion","humedad","uv","luz","optimo"]:
                send_serial_command(command)
    except WebSocketDisconnect:
        if websocket in clients:
            clients.remove(websocket)

async def realtime_broadcaster():
    if SIMULATE:
        import random
        while True:
            data={"temperature":round(random.uniform(20,35),2),"humidity":round(random.uniform(35,75),2),"light":random.randint(0,800),"mode_index":current_mode_index,"mode":get_mode(),"simulated":True}
            data_str=json.dumps(data)
            save_reading(data_str)
            await broadcast(data_str)
            await asyncio.sleep(1)

@asynccontextmanager
async def lifespan(app):
    global app_loop
    app_loop=asyncio.get_running_loop()
    task=asyncio.create_task(realtime_broadcaster())
    yield
    task.cancel()

app.router.lifespan_context=lifespan

if __name__=="__main__":
    import uvicorn
    uvicorn.run(app,host="0.0.0.0",port=8000)