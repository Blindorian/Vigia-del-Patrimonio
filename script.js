const terminal = document.getElementById('terminalConsole');
const serialStatusIndicator = document.getElementById('serialStatusIndicator');
const statusDot = document.getElementById('statusDot');
const connectBtn = document.getElementById('connectBtn');
let ws = null;

// Escribir en terminal
function writeToTerminal(message, type = 'data') {
    const p = document.createElement('p');
    const time = new Date().toLocaleTimeString('es-ES', { hour12: false });
    p.innerHTML = `<span style="color: #64748b;">[${time}]</span> <span class="log-${type}">${message}</span>`;
    terminal.appendChild(p);
    terminal.scrollTop = terminal.scrollHeight;
}

// Actualizar UI según los umbrales tolerados en clima tropical
function updateStatus(id, value, safeMin, safeMax, dangerLimit) {
    const el = document.getElementById(id);
    if (value >= dangerLimit || value <= safeMin / 2) {
        el.className = 'status status-alert';
        el.innerText = 'Riesgo Crítico';
    } else if (value >= safeMax || value <= safeMin) {
        el.className = 'status status-warn';
        el.innerText = 'Atención Requerida';
    } else {
        el.className = 'status status-safe';
        el.innerText = 'Condiciones Óptimas';
    }
}

// Procesar los datos de los sensores e iluminar el panel
function processData(data) {
    writeToTerminal(`RX -> ${JSON.stringify(data)}`, 'data');

    // Procesar Temperatura
    if (data.temperature !== undefined) {
        const temp = data.temperature;
        document.getElementById('tempValue').innerHTML = temp.toFixed(1) + '<span>°C</span>';
        updateStatus('tempStatus', temp, 18, 25, 28);
        document.getElementById('tempValue').style.color = temp >= 28 ? 'var(--accent-danger)' : 'var(--text-main)';
    }

    // Procesar Humedad Relativa
    if (data.humidity !== undefined) {
        const hum = data.humidity;
        document.getElementById('humValue').innerHTML = hum.toFixed(1) + '<span>%</span>';
        updateStatus('humStatus', hum, 40, 60, 70);
        document.getElementById('humValue').style.color = hum >= 70 ? 'var(--accent-danger)' : 'var(--text-main)';
    } else if (data.simulated && data.temperature !== undefined) {
        // Fallback inteligente por si se parsea texto plano incompleto
        const hum = data.temperature > 30 ? 20.1 : 50.0;
        document.getElementById('humValue').innerHTML = hum.toFixed(1) + '<span>%</span>';
        updateStatus('humStatus', hum, 40, 60, 70);
    }

    // Procesar Exposición Lumínica / UV
    if (data.light !== undefined) {
        const light = data.light;
        document.getElementById('lightValue').innerHTML = light + '<span>lx</span>';
        updateStatus('lightStatus', light, 0, 500, 800);
        document.getElementById('lightValue').style.color = light >= 800 ? 'var(--accent-warn)' : 'var(--text-main)';
    }
}

// Simulación de escenarios críticos enviados al backend
function triggerScenario(type) {
    writeToTerminal(`[COMANDO] Enviando escenario: ${type.toUpperCase()}`, 'warn');
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ command: type }));
    } else {
        writeToTerminal('Esperando conexión con el backend...', 'error');
    }
}

// Conexión WebSockets al Backend de Python
connectBtn.addEventListener('click', () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
        writeToTerminal('Ya estás conectado, panita.', 'warn');
        return;
    }

    writeToTerminal('Intentando conectar al backend...', 'info'); // Cambiado a 'info' con estilo propio
    ws = new WebSocket("ws://localhost:8000/ws");

    ws.onopen = function() {
        writeToTerminal('Conexión WS establecida con éxito.', 'safe');
        connectBtn.innerText = "Monitoreo Activo";
        connectBtn.classList.add('connected');
        serialStatusIndicator.innerText = "CONECTADO A BACKEND";
        statusDot.classList.add('active');
    };

    ws.onmessage = function(event) {
        try {
            // Caso ideal: El backend manda JSON estructurado
            const data = JSON.parse(event.data);
            processData(data);
        } catch (e) {
            // Caso de emergencia: Parseo de strings crudos desde la Micro:bit
            const textData = event.data;
            let dataToProcess = {};
            
            const tempMatch = textData.match(/(?:T:|Temp|Tempe?ratura|Temeratura)[\s:=]*([\d.]+)/i);
            if (tempMatch) dataToProcess.temperature = parseFloat(tempMatch[1]);
            
            const humMatch = textData.match(/(?:H:|Hum|Humedad)[\s:=]*([\d.]+)/i);
            if (humMatch) dataToProcess.humidity = parseFloat(humMatch[1]);
            
            const lightMatch = textData.match(/(?:L:|Lz|Luz)[\s:=]*([\d.]+)/i);
            if (lightMatch) dataToProcess.light = parseInt(lightMatch[1]);
            
            // Avisamos a la lógica que es un dato simulado/forzado para evitar cuelgues
            dataToProcess.simulated = true;
            
            processData(dataToProcess);
        }
    };

    ws.onclose = function() {
        writeToTerminal('Conexión WS cerrada.', 'error');
        connectBtn.innerText = "Reconectar";
        connectBtn.classList.remove('connected');
        serialStatusIndicator.innerText = "DESCONECTADO";
        statusDot.classList.remove('active');
    };

    ws.onerror = function(err) {
        writeToTerminal('Error de conexión WS. ¿Está ejecutándose backend.py, compa?', 'error');
    };
});

//pana panita pana