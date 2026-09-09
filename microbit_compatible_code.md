```python
hum_c=0
temp_c=0
luz=0
humedad=0
temperatura=0
simulacion_activa=False
estado="verde"
modo_actual=0
TOTAL_MODOS=3

MODO_PAPEL=0
MODO_TEXTILES=1
MODO_METAL=2

PIN_BUZZER=DigitalPin.P16
PIN_LDR=AnalogPin.P1
PIN_DHT=DigitalPin.P0
ES_ANODO_COMUN=False

PAPEL_TEMP_MIN=18
PAPEL_TEMP_MAX=25
PAPEL_TEMP_CRITICA_BAJA=14
PAPEL_TEMP_CRITICA_ALTA=30
PAPEL_HUM_MIN=40
PAPEL_HUM_MAX=60
PAPEL_HUM_CRITICA_BAJA=30
PAPEL_HUM_CRITICA_ALTA=75
PAPEL_LUZ_WARN=500
PAPEL_LUZ_CRITICA=800

TEXTIL_TEMP_MIN=18
TEXTIL_TEMP_MAX=21
TEXTIL_TEMP_CRITICA_BAJA=14
TEXTIL_TEMP_CRITICA_ALTA=26
TEXTIL_HUM_MIN=45
TEXTIL_HUM_MAX=55
TEXTIL_HUM_CRITICA_BAJA=35
TEXTIL_HUM_CRITICA_ALTA=70
TEXTIL_LUZ_WARN=50
TEXTIL_LUZ_CRITICA=100

METAL_TEMP_MIN=18
METAL_TEMP_MAX=25
METAL_TEMP_CRITICA_BAJA=10
METAL_TEMP_CRITICA_ALTA=30
METAL_HUM_MIN=40
METAL_HUM_MAX=55
METAL_HUM_CRITICA_BAJA=25
METAL_HUM_CRITICA_ALTA=70
METAL_LUZ_WARN=300
METAL_LUZ_CRITICA=600


def set_rgb(r:number,g:number,b:number):
    if ES_ANODO_COMUN:
        pins.digital_write_pin(DigitalPin.P8,1-r)
        pins.digital_write_pin(DigitalPin.P12,1-g)
        pins.digital_write_pin(DigitalPin.P13,1-b)
    else:
        pins.digital_write_pin(DigitalPin.P8,r)
        pins.digital_write_pin(DigitalPin.P12,g)
        pins.digital_write_pin(DigitalPin.P13,b)

def nombre_modo():
    if modo_actual==MODO_PAPEL:
        return "Papel"
    elif modo_actual==MODO_TEXTILES:
        return "Textiles"
    elif:
        return "Metal"

def enviar_modo():
    serial.write_line('{"type":"mode","mode_index":'+str(modo_actual)+',"mode":"'+nombre_modo()+'"}')
    
def cambiar_modo():
    global modo_actual
    modo_actual=(modo_actual+1)%TOTAL_MODOS
    enviar_modo()
    mostrar_modo()
    basic.clear_screen()

input.on_button_pressed(Button.B,cambiar_modo)

def on_button_pressed_a():
    actualizar_sensores()
    serial.write_line('{"type":"manual","temperature":'+str(temperatura)+',"humidity":'+str(humedad)+',"light":'+str(luz)+',"mode_index":'+str(modo_actual)+'}')
    basic.show_icon(IconNames.YES)
    basic.pause(100)
    basic.clear_screen()

input.on_button_pressed(Button.A,on_button_pressed_a)

def actualizar_sensores():
    global luz
    luz = pins.analog_read_pin(PIN_LDR)
    # global luz,temp_c,hum_c,temperatura,humedad
    #luz=pins.analog_read_pin(PIN_LDR)
    #basic.pause(100)
    #dht11_dht22.query_data(DHTtype.DHT11,PIN_DHT,True,False,True)
    #temp_c=dht11_dht22.read_data(dataType.TEMPERATURE)
    #hum_c=dht11_dht22.read_data(dataType.HUMIDITY)
    #if temp_c!=-999:
    #    temperatura=temp_c
    #if hum_c!=-999:
    #    humedad=hum_c

def on_data_received():
    global temperatura,humedad,luz,simulacion_activa,modo_actual

    comando=serial.read_until(
        serial.delimiters(Delimiters.NEW_LINE)
    ).strip()

    comando_upper=comando.upper()

    if comando_upper.startswith("MODO:") or comando_upper.startswith("MODE:"):
        try:
            nuevo_modo=int(comando.split(":")[1].strip())

            if nuevo_modo>=0 and nuevo_modo<TOTAL_MODOS:
                modo_actual=nuevo_modo
                enviar_modo()

        except:
            pass
    elif comando=="incendio":
        simulacion_activa=True
        temperatura=45.5
        humedad=20.1
        luz=850
    elif comando=="inundacion":
        simulacion_activa=True
        temperatura=18.2
        humedad=88.5
        luz=150
    elif comando=="humedad":
        simulacion_activa=True
        temperatura=24
        humedad=88
        luz=150
    elif comando=="uv" or comando=="luz":
        simulacion_activa=True
        temperatura=26
        humedad=55
        luz=950
    elif comando=="optimo":
        simulacion_activa=False

serial.on_data_received(serial.delimiters(Delimiters.NEW_LINE),on_data_received)

def evaluar_riesgo():
    global estado
    critico=False
    advertencia=False
    if modo_actual==MODO_PAPEL:
        if temperatura<=PAPEL_TEMP_CRITICA_BAJA or temperatura>=PAPEL_TEMP_CRITICA_ALTA or humedad<=PAPEL_HUM_CRITICA_BAJA or humedad>=PAPEL_HUM_CRITICA_ALTA or luz>=PAPEL_LUZ_CRITICA:
            critico=True
        elif temperatura<PAPEL_TEMP_MIN or temperatura>PAPEL_TEMP_MAX or humedad<PAPEL_HUM_MIN or humedad>PAPEL_HUM_MAX or luz>=PAPEL_LUZ_WARN:
            advertencia=True
    elif modo_actual==MODO_TEXTILES:
        if temperatura<=TEXTIL_TEMP_CRITICA_BAJA or temperatura>=TEXTIL_TEMP_CRITICA_ALTA or humedad<=TEXTIL_HUM_CRITICA_BAJA or humedad>=TEXTIL_HUM_CRITICA_ALTA or luz>=TEXTIL_LUZ_CRITICA:
            critico=True
        elif temperatura<TEXTIL_TEMP_MIN or temperatura>TEXTIL_TEMP_MAX or humedad<TEXTIL_HUM_MIN or humedad>TEXTIL_HUM_MAX or luz>=TEXTIL_LUZ_WARN:
            advertencia=True
    elif modo_actual==MODO_METAL:
        if temperatura<=METAL_TEMP_CRITICA_BAJA or temperatura>=METAL_TEMP_CRITICA_ALTA or humedad<=METAL_HUM_CRITICA_BAJA or humedad>=METAL_HUM_CRITICA_ALTA or luz>=METAL_LUZ_CRITICA:
            critico=True
        elif temperatura<METAL_TEMP_MIN or temperatura>METAL_TEMP_MAX or humedad<METAL_HUM_MIN or humedad>METAL_HUM_MAX or luz>=METAL_LUZ_WARN:
            advertencia=True
    
    if critico:
        estado="rojo"
        pins.digital_write_pin(PIN_BUZZER,1)
        set_rgb(1,0,0)
    elif advertencia:
        estado="amarillo"
        pins.digital_write_pin(PIN_BUZZER,0)
        set_rgb(1,1,0)
    else:
        estado="verde"
        pins.digital_write_pin(PIN_BUZZER,0)
        set_rgb(0,1,0)

def on_forever():
    if not simulacion_activa:
        actualizar_sensores()
    evaluar_riesgo()
    serial.write_line('{"temperature":'+str(temperatura)+',"humidity":'+str(humedad)+',"light":'+str(luz)+',"mode_index":'+str(modo_actual)+'}')
    basic.pause(1500)

basic.forever(on_forever)
```