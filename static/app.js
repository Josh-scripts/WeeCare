const ws = new WebSocket(`ws://${window.location.host}/ws`);

const connStatus = document.getElementById('connection-status');
const connDot = document.getElementById('connection-dot');

const brValue = document.getElementById('br-value');
const hrValue = document.getElementById('hr-value');
const moveValue = document.getElementById('movement-value');
const alertValue = document.getElementById('alert-value');
const alertBar = document.getElementById('alert-bar');
const heartIcon = document.querySelector('.heart-icon');

// Canvas Setup
const canvas = document.getElementById('raw-signal-canvas');
const ctx = canvas.getContext('2d');
const MAX_DATA_POINTS = 150;
let rawData = new Array(MAX_DATA_POINTS).fill(0);

function resizeCanvas() {
    canvas.width = canvas.parentElement.clientWidth;
    canvas.height = canvas.parentElement.clientHeight;
}
window.addEventListener('resize', resizeCanvas);
// Call once after a slight delay to ensure CSS has applied
setTimeout(resizeCanvas, 100);

ws.onopen = () => {
    connStatus.textContent = 'Live (20Hz)';
    connDot.className = 'dot connected';
    heartIcon.classList.add('beating');
};

ws.onclose = () => {
    connStatus.textContent = 'Disconnected';
    connDot.className = 'dot disconnected';
    heartIcon.classList.remove('beating');
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    // Update Values
    brValue.textContent = data.breathingRate.toFixed(1);
    
    // Modulate heart icon speed based on HR
    const beatDuration = 60 / data.heartRate;
    heartIcon.style.animationDuration = `${beatDuration}s`;
    hrValue.textContent = data.heartRate.toFixed(1);
    
    // Movement Logic
    moveValue.textContent = data.movement;
    if(data.movement === 'FALL') {
        moveValue.className = 'color-red';
    } else if(data.movement === 'POSITIONAL') {
        moveValue.className = 'color-yellow';
    } else {
        moveValue.className = 'color-white';
    }
    
    // Alert Logic
    const alertPercent = (data.alert * 100).toFixed(0);
    alertValue.textContent = `${alertPercent}%`;
    alertBar.style.width = `${alertPercent}%`;
    if(data.alert > 0.8) {
        alertValue.className = 'color-red';
    } else {
        alertValue.className = 'color-white';
    }
    
    // Update Canvas
    rawData.push(data.signal_raw);
    if(rawData.length > MAX_DATA_POINTS) {
        rawData.shift();
    }
    drawChart();
};

function drawChart() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.beginPath();
    ctx.strokeStyle = '#38bdf8';
    ctx.lineWidth = 3;
    
    const sliceWidth = canvas.width / (rawData.length - 1);
    let x = 0;
    
    // Auto-scale logic
    const minVal = Math.min(...rawData);
    const maxVal = Math.max(...rawData);
    const range = (maxVal - minVal) || 1;
    
    for(let i = 0; i < rawData.length; i++) {
        // Normalize between 0 and 1, flip y axis
        const normalized = (rawData[i] - minVal) / range;
        const y = canvas.height - (normalized * canvas.height * 0.8 + canvas.height * 0.1);
        
        if(i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
        
        x += sliceWidth;
    }
    
    // Add glow
    ctx.shadowBlur = 15;
    ctx.shadowColor = '#38bdf8';
    ctx.stroke();
    ctx.shadowBlur = 0;
}
