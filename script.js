const terminal=document.getElementById('terminalConsole');
const serialStatusIndicator=document.getElementById('serialStatusIndicator');
const statusDot=document.getElementById('statusDot');
const connectBtn=document.getElementById('connectBtn');
const modeBtn=document.getElementById('modeBtn');
const modeName=document.getElementById('modeName');
let ws=null;
let currentModeIndex=0;

const MODES=[
    {name:'Papel',temperature:{safeMin:18,safeMax:25,warnMin:16,warnMax:28,criticalMin:14,criticalMax:30},humidity:{safeMin:40,safeMax:60,warnMin:35,warnMax:70,criticalMin:30,criticalMax:75},light:{safeMax:500,warnMax:500,criticalMax:800}},
    {name:'Textiles',temperature:{safeMin:18,safeMax:21,warnMin:16,warnMax:24,criticalMin:14,criticalMax:26},humidity:{safeMin:45,safeMax:55,warnMin:40,warnMax:65,criticalMin:35,criticalMax:70},light:{safeMax:50,warnMax:50,criticalMax:100}},
    {name:'Metal',temperature:{safeMin:18,safeMax:25,warnMin:15,warnMax:28,criticalMin:10,criticalMax:30},humidity:{safeMin:40,safeMax:55,warnMin:30,warnMax:65,criticalMin:25,criticalMax:70},light:{safeMax:300,warnMax:300,criticalMax:600}},
];

function writeToTerminal(message,type='data'){
    const p=document.createElement('p');
    const time=new Date().toLocaleTimeString('es-ES',{hour12:false});
    p.innerHTML=`<span style="color:#64748b;">[${time}]</span> <span class="log-${type}">${message}</span>`;
    terminal.appendChild(p);
    terminal.scrollTop=terminal.scrollHeight;
}

function setMode(index,announce=true){
    index=parseInt(index);
    if(isNaN(index)||index<0||index>=MODES.length) index=0;
    currentModeIndex=index;
    const mode=MODES[currentModeIndex];
    modeBtn.textContent=`Modo: ${mode.name}`;
    modeName.textContent=mode.name;
    if(announce) writeToTerminal(`[MODO] Monitoreando: ${mode.name}`,'info');
    refreshStatuses();
}

function requestNextMode(){
    if(!ws||ws.readyState!==WebSocket.OPEN){
        writeToTerminal('Conecta primero el Backend para cambiar el modo del sistema.','error');
        return;
    }
    writeToTerminal('[COMANDO] Cambiando al siguiente material...','info');
    ws.send(JSON.stringify({command:'cambiar_modo'}));
}

modeBtn.addEventListener('click',requestNextMode);

function getRisk(value,limits,isLight=false){
    if(isLight){
        if(value>=limits.criticalMax)return 'critical';
        if(value>=limits.warnMax)return 'warning';
        return 'safe';
    }
    if(value<=limits.criticalMin||value>=limits.criticalMax)return 'critical';
    if(value<=limits.warnMin||value>=limits.warnMax)return 'warning';
    return 'safe';
}

function updateStatus(id,value,limits,isLight=false){
    const el=document.getElementById(id);
    const risk=getRisk(value,limits,isLight);
    if(risk==='critical'){
        el.className='status status-alert';
        el.innerText='Riesgo Crítico';
    }else if(risk==='warning'){
        el.className='status status-warn';
        el.innerText='Atención Requerida';
    }else{
        el.className='status status-safe';
        el.innerText='Condiciones Óptimas';
    }
}

function updateValueColor(id,value,limits,isLight=false){
    const el=document.getElementById(id);
    const risk=getRisk(value,limits,isLight);
    if(risk==='critical')el.style.color='var(--accent-danger)';
    else if(risk==='warning')el.style.color='var(--accent-warn)';
    else el.style.color='var(--text-main)';
}

let lastData={};

function refreshStatuses(){
    const mode=MODES[currentModeIndex];
    if(lastData.temperature!==undefined){
        updateStatus('tempStatus',lastData.temperature,mode.temperature);
        updateValueColor('tempValue',lastData.temperature,mode.temperature);
    }
    if(lastData.humidity!==undefined){
        updateStatus('humStatus',lastData.humidity,mode.humidity);
        updateValueColor('humValue',lastData.humidity,mode.humidity);
    }
    if(lastData.light!==undefined){
        updateStatus('lightStatus',lastData.light,mode.light,true);
        updateValueColor('lightValue',lastData.light,mode.light,true);
    }
}

function processData(data){
    writeToTerminal(`RX -> ${JSON.stringify(data)}`,'data');
    if(data.mode_index!==undefined)setMode(data.mode_index,false);
    if(data.temperature!==undefined){
        const temp=parseFloat(data.temperature);
        lastData.temperature=temp;
        document.getElementById('tempValue').innerHTML=temp.toFixed(1)+'<span>°C</span>';
    }
    if(data.humidity!==undefined){
        const hum=parseFloat(data.humidity);
        lastData.humidity=hum;
        document.getElementById('humValue').innerHTML=hum.toFixed(1)+'<span>%</span>';
    }
    if(data.light!==undefined){
        const light=parseInt(data.light);
        lastData.light=light;
        document.getElementById('lightValue').innerHTML=light+'<span>lx</span>';
    }
    refreshStatuses();
}

function triggerScenario(type){
    writeToTerminal(`[COMANDO] Enviando escenario: ${type.toUpperCase()}`,'warn');
    if(ws&&ws.readyState===WebSocket.OPEN)ws.send(JSON.stringify({command:type}));
    else writeToTerminal('Esperando conexión con el backend...','error');
}

connectBtn.addEventListener('click',()=>{
    if(ws&&ws.readyState===WebSocket.OPEN){
        writeToTerminal('Ya estás conectado.','warn');
        return;
    }
    writeToTerminal('Intentando conectar al backend...','info');
    ws=new WebSocket('ws://localhost:8000/ws');
    ws.onopen=()=>{
        writeToTerminal('Conexión WS establecida con éxito.','safe');
        connectBtn.innerText='Monitoreo Activo';
        connectBtn.classList.add('connected');
        serialStatusIndicator.innerText='CONECTADO A BACKEND';
        statusDot.classList.add('active');
    };
    ws.onmessage=event=>{
        try{
            const data=JSON.parse(event.data);
            if(data.type==='mode'){
                setMode(data.mode_index,true);
                return;
            }
            processData(data);
        }catch(e){
            const textData=event.data;
            const data={};
            const tempMatch=textData.match(/(?:T:|Temp|Tempe?ratura|Temeratura)[\s:=]*([\d.]+)/i);
            const humMatch=textData.match(/(?:H:|Hum|Humedad)[\s:=]*([\d.]+)/i);
            const lightMatch=textData.match(/(?:L:|Lz|Luz)[\s:=]*([\d.]+)/i);
            const modeMatch=textData.match(/(?:MODO|MODE)[\s:=]*(\d+)/i);
            if(tempMatch)data.temperature=parseFloat(tempMatch[1]);
            if(humMatch)data.humidity=parseFloat(humMatch[1]);
            if(lightMatch)data.light=parseInt(lightMatch[1]);
            if(modeMatch)data.mode_index=parseInt(modeMatch[1]);
            processData(data);
        }
    };
    ws.onclose=()=>{
        writeToTerminal('Conexión WS cerrada.','error');
        connectBtn.innerText='Reconectar';
        connectBtn.classList.remove('connected');
        serialStatusIndicator.innerText='DESCONECTADO';
        statusDot.classList.remove('active');
    };
    ws.onerror=()=>{
        writeToTerminal('Error de conexión WS. ¿Está ejecutándose backend.py?','error');
    };
});

setMode(0,false);