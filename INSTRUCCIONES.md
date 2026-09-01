# Documentación Final: Vigía del Patrimonio

Este repositorio contiene la arquitectura completa de IoT para la monitorización bidireccional y preventiva de bienes culturales.

## 1. Archivos Principales
*   **`backend.py`**: Servidor local hecho en FastAPI. Sirve como puente entre la página web (WebSockets) y la Micro:bit (Serial).
*   **`Vigía del Patrimonio _ Panel de Control.html`**: El panel de control visual. Se conecta al backend para mostrar telemetría y enviar comandos de simulación.
*   **`microbit_compatible_code.md`**: El código oficial en Python para MakeCode.
*   **`db_manager.py`**: Script de consola para gestionar la base de datos de telemetría.
*   **`requirements.txt`**: Las dependencias de Python necesarias.

## 2. Instalación de Dependencias
Abre tu consola/terminal en la carpeta del proyecto y ejecuta:
```bash
pip install -r requirements.txt
```

## 3. Ejecución del Sistema
1.  **Carga el código en la Micro:bit**: Utiliza el código que guardamos en MakeCode, pásalo a la placa y asegúrate de cerrar la pestaña de Serial en el navegador para no bloquear el puerto COM.
2.  **Inicia el Servidor Puente**:
    ```bash
    python backend.py
    ```
    *Verás el mensaje de que el Micro:bit fue detectado y conectado exitosamente en el COMx correspondiente.*
3.  **Abre el Panel**: Da doble clic en el archivo HTML `Vigía del Patrimonio _ Panel de Control.html`.
4.  Presiona **Conectar Backend** en la página. ¡Listo! Los datos empezarán a fluir.

## 4. Gestión de Base de Datos (SQLite)
El archivo `backend.py` guarda automáticamente todas las lecturas de la Micro:bit en un archivo local llamado `sensor_data.db`. Esto permite tener un histórico sin colapsar la memoria de la placa.

Si con el tiempo el archivo se vuelve muy pesado (muchos megabytes), puedes limpiarlo utilizando el script de mantenimiento. Simplemente corre:
```bash
python db_manager.py
```
Este script te permitirá ver los registros más recientes o **vaciar por completo** la base de datos para recuperar espacio y velocidad en tu disco duro (incluye el comando `VACUUM` de SQLite que comprime el archivo tras el borrado).
