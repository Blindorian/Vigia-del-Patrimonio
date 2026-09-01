# Integración Bidireccional: Micro:bit y Panel Web

Para que tu Micro:bit entienda las simulaciones que envías desde la página web (a través de nuestro nuevo Backend de Python), necesitamos actualizar ligeramente su código. 

## ¿Qué cambia en el código?
1. **Modo Simulación:** Agregamos una variable global `simulacion_activa`. 
2. **Recepción Serial:** Usamos la función `serial.on_data_received` para "escuchar" la terminal.
3. **Pausa de Hardware:** Cuando la placa recibe un comando como `"incendio"`, activa el modo simulación. Esto significa que **deja de leer los sensores físicos** y adopta los valores catastróficos, activando físicamente los LEDs y el Buzzer tal como si estuviera sucediendo de verdad. 
4. **Comando `"optimo"`:** Apaga el modo simulación y obliga al Micro:bit a volver a hacerle caso a sus sensores de hardware.

## Código en Python (MakeCode)

Copia y pega este código en la vista de **Python** dentro de MakeCode:

```python
"""
--- VARIABLES GLOBALES ---
"""
hum_c = 0
temp_c = 0
luz = 0
humedad = 0
temperatura = 0
simulacion_activa = False

# --- CONFIGURACIÓN DE PINES ---
PIN_BUZZER = DigitalPin.P16
PIN_LDR = AnalogPin.P1
PIN_DHT = DigitalPin.P0

# --- CONFIGURACIÓN DE LED ---
ES_ANODO_COMUN = False
estado = "verde"

# --- UMBRALES ---
TEMP_CRITICA = 28
HUM_CRITICA = 70
LUZ_CRITICA = 800

def on_button_pressed_a():
    # Fuerza una lectura manual fuera del ciclo automático.
    actualizar_sensores()
    serial.write_line("MANUAL -> T:" + str(temperatura) + " H:" + str(humedad) + " L:" + str(luz))
    basic.show_icon(IconNames.YES)
    basic.pause(100)
    basic.clear_screen()
input.on_button_pressed(Button.A, on_button_pressed_a)

def set_rgb(r: number, g: number, b: number):
    # Controla el LED ajustando la lógica matemáticamente.
    if ES_ANODO_COMUN:
        pins.digital_write_pin(DigitalPin.P8, 1 - r) # Rojo
        pins.digital_write_pin(DigitalPin.P12, 1 - g) # Verde
        pins.digital_write_pin(DigitalPin.P13, 1 - b) # Azul
    else:
        pins.digital_write_pin(DigitalPin.P8, r)
        pins.digital_write_pin(DigitalPin.P12, g)
        pins.digital_write_pin(DigitalPin.P13, b)

def actualizar_sensores():
    global luz, temp_c, hum_c, temperatura, humedad
    # 1. Leer LDR
    luz = pins.analog_read_pin(PIN_LDR)
    basic.pause(100)
    # 2. Leer DHT
    dht11_dht22.query_data(DHTtype.DHT11, PIN_DHT, True, False, True)
    temp_c = dht11_dht22.read_data(dataType.TEMPERATURE)
    hum_c = dht11_dht22.read_data(dataType.HUMIDITY)
    # 3. Filtros anti-error
    if temp_c != -999:
        temperatura = temp_c
    if hum_c != -999:
        humedad = hum_c

# --- NUEVO: RECEPTOR DE COMANDOS DESDE EL PANEL WEB ---
def on_data_received():
    global temperatura, humedad, luz, simulacion_activa
    comando = serial.read_until(serial.delimiters(Delimiters.NEW_LINE)).strip()
    
    if comando == "incendio":
        simulacion_activa = True
        temperatura = 45.5
        humedad = 20.1
        luz = 850
    elif comando == "inundacion":
        simulacion_activa = True
        temperatura = 18.2
        humedad = 88.5
        luz = 150
    elif comando == "luz":
        simulacion_activa = True
        temperatura = 26.0
        humedad = 55.0
        luz = 950
    elif comando == "optimo":
        simulacion_activa = False # Volver a leer los sensores físicos reales

serial.on_data_received(serial.delimiters(Delimiters.NEW_LINE), on_data_received)


def on_forever():
    global estado
    
    # Solo leemos los sensores reales si NO estamos en una simulación web
    if not simulacion_activa:
        actualizar_sensores()
        
    # Lógica de estados y alertas (Aplica para datos reales o simulados)
    if temperatura >= TEMP_CRITICA or humedad >= HUM_CRITICA or luz >= LUZ_CRITICA:
        estado = "rojo"
        pins.digital_write_pin(PIN_BUZZER, 1) # Buzzer ON
        set_rgb(1, 0, 0)
    else:
        estado = "verde"
        pins.digital_write_pin(PIN_BUZZER, 0) # Buzzer OFF
        set_rgb(0, 1, 0)
        
    # Telemetría empaquetada enviada al servidor de Python
    serial.write_line("T:" + str(temperatura) + " H:" + str(humedad) + " L:" + str(luz))
    
    # Pausas de seguridad y Buffer
    basic.pause(100)
    basic.pause(1000) # Reducido a 1 segundo para evitar bloqueos largos

basic.forever(on_forever)
```

## Resumen del Flujo de Trabajo
1. En tu Panel Web haces clic en **Conato de Incendio**.
2. Tu JavaScript manda la señal JSON por WebSocket (`{"command": "incendio"}`).
3. Tu archivo `backend.py` lee esto y le susurra al cable USB: `"incendio\n"`.
4. El Micro:bit dispara `on_data_received()`, apaga los sensores físicos momentáneamente (`simulacion_activa = True`), inyecta los valores críticos y **enciende tu buzzer y LEDs físicos**.
5. ¡Toda la simulación se experimenta a nivel de hardware y software al mismo tiempo! Cuando terminas, oprimes **Restaurar Óptimo** y la placa vuelve a la normalidad.
