import serial
import time

print("Abriendo COM4...")

ser = serial.Serial(
    "COM4",
    115200,
    timeout=1
)

print("COM4 ABIERTO")
print("Escuchando...")

while True:
    try:
        data = ser.readline()

        if data:
            print("RX:", repr(data))

    except Exception as e:
        print("ERROR:", repr(e))
        break