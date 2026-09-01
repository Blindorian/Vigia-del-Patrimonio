import sqlite3
import os

DB_FILE = "sensor_data.db"

def ver_registros(limite=10):
    if not os.path.exists(DB_FILE):
        print("La base de datos aún no existe.")
        return
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM readings ORDER BY id DESC LIMIT ?", (limite,))
    rows = c.fetchall()
    print(f"\n--- ÚLTIMOS {limite} REGISTROS ---")
    for r in rows:
        print(f"ID: {r[0]} | Timestamp: {r[1]} | Dato: {r[2]}")
    conn.close()

def limpiar_base():
    if not os.path.exists(DB_FILE):
        print("La base de datos aún no existe.")
        return
    confirm = input("¿Estás seguro de borrar TODOS los datos históricos? (s/n): ")
    if confirm.lower() == 's':
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM readings")
        c.execute("VACUUM") # Libera espacio físico en disco
        conn.commit()
        conn.close()
        print("Base de datos limpiada y comprimida correctamente.")
    else:
        print("Operación cancelada.")

if __name__ == "__main__":
    while True:
        print("\n=== GESTIÓN DE BASE DE DATOS (Vigía del Patrimonio) ===")
        print("1. Ver últimos registros")
        print("2. Limpiar todos los datos (Evitar saturación de disco)")
        print("3. Salir")
        opcion = input("Elige una opción: ")
        
        if opcion == "1":
            ver_registros(15)
        elif opcion == "2":
            limpiar_base()
        elif opcion == "3":
            print("Saliendo...")
            break
        else:
            print("Opción inválida.")
