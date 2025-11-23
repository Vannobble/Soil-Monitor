# server.py - Diperbaiki untuk real-time updates
from flask import Flask, render_template
from flask_socketio import SocketIO
from flask_cors import CORS
import paho.mqtt.client as mqtt
import json
import binascii
import ascon
import os
from datetime import datetime
import logging
import time
import eventlet

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'soil_moisture_secret_production')
CORS(app)

eventlet.monkey_patch()

# Socket.IO dengan configuration yang benar
socketio = SocketIO(app, 
                   cors_allowed_origins="*",
                   async_mode='eventlet',
                   ping_timeout=300,  # Increase timeout
                   ping_interval=60,
                   max_http_buffer_size=1e8,  # Increase buffer size
                   logger=False,  # Disable logger in production
                   engineio_logger=False)

# Konfigurasi dari Environment Variables
key = os.environ.get('ASCON_KEY', 'asconciphertest1').encode('utf-8')
nonce = os.environ.get('ASCON_NONCE', 'asconcipher1test').encode('utf-8')
associateddata = os.environ.get('ASCON_AD', 'ASCON').encode('utf-8')
variant = os.environ.get('ASCON_VARIANT', 'Ascon-128')

# MQTT Configuration
MQTT_BROKER = os.environ.get('MQTT_BROKER', 'broker.hivemq.com')
MQTT_PORT = int(os.environ.get('MQTT_PORT', 1883))
MQTT_TOPIC = os.environ.get('MQTT_TOPIC', 'soil-ascon128')

# Store data terakhir dan connected clients
last_data = {
    'moisture': 0,
    'sensor': 'soil_moisture',
    'unit': '%',
    'encrypted': '',
    'timestamp': None,
    'message_count': 0
}

connected_clients = 0

def on_mqtt_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info(f"✅ Connected to MQTT broker: {MQTT_BROKER}")
        client.subscribe(MQTT_TOPIC)
        logger.info(f"🎯 Subscribed to topic: {MQTT_TOPIC}")
    else:
        logger.error(f"❌ Failed to connect to MQTT, return code: {rc}")

def on_mqtt_message(client, userdata, msg):
    global last_data
    try:
        logger.info(f"📨 Received MQTT message from topic: {msg.topic}")
        
        data = json.loads(msg.payload.decode())
        encrypted_hex = data['data']
        
        logger.info(f"🔐 Encrypted data received: {encrypted_hex[:20]}...")
        
        # Dekripsi data
        encrypted_bytes = binascii.unhexlify(encrypted_hex)
        decrypted_bytes = ascon.demo_aead_p(variant, encrypted_bytes)
        
        if decrypted_bytes:
            moisture_value = int.from_bytes(decrypted_bytes, 'big')
            
            # Update last data
            last_data = {
                'moisture': moisture_value,
                'sensor': data.get('sensor', 'soil_moisture'),
                'unit': data.get('unit', '%'),
                'encrypted': encrypted_hex,
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'message_count': last_data['message_count'] + 1
            }
            
            logger.info(f"✅ Decrypted moisture value: {moisture_value}%")
            
            # Kirim ke semua connected clients
            socketio.emit('sensor_data', last_data, broadcast=True)
            logger.info(f"📤 Sent to {connected_clients} connected clients via Socket.IO")
            
        else:
            logger.error("❌ Decryption failed!")
            
    except Exception as e:
        logger.error(f"❌ Error processing MQTT message: {e}")
        import traceback
        traceback.print_exc()

# Setup MQTT client
mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_mqtt_connect
mqtt_client.on_message = on_mqtt_message

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return {
        'status': 'healthy',
        'last_update': last_data['timestamp'],
        'message_count': last_data['message_count'],
        'connected_clients': connected_clients,
        'service': 'soil-moisture-monitor'
    }

@app.route('/api/data')
def api_data():
    return last_data

@socketio.on('connect')
def handle_connect():
    global connected_clients
    connected_clients += 1
    logger.info(f'✅ Client connected. Total clients: {connected_clients}')
    
    # Kirim data terakhir ke client baru
    socketio.emit('sensor_data', last_data)
    logger.info('📤 Sent last data to new client')

@socketio.on('disconnect')
def handle_disconnect():
    global connected_clients
    connected_clients -= 1
    logger.info(f'❌ Client disconnected. Total clients: {connected_clients}')

@socketio.on('request_data')
def handle_request_data():
    """Client meminta data terbaru"""
    socketio.emit('sensor_data', last_data)
    logger.info('📤 Sent data on client request')

def start_mqtt():
    try:
        logger.info(f"🔄 Connecting to MQTT broker: {MQTT_BROKER}:{MQTT_PORT}")
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
        logger.info("✅ MQTT client started successfully")
    except Exception as e:
        logger.error(f"❌ MQTT connection failed: {e}")

if __name__ == '__main__':
    start_mqtt()
    port = int(os.environ.get('PORT', 5000))
    
    # Konfigurasi untuk production
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    
    logger.info(f"🚀 Starting production server on port {port}")
    
    socketio.run(app, 
                 host='0.0.0.0', 
                 port=port, 
                 debug=debug_mode,
                 use_reloader=False,
                 log_output=False)  # Disable log output for better performance
