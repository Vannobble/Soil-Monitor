# server.py - Production Ready
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

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'soil_moisture_secret_production')
CORS(app)
socketio = SocketIO(app, 
                   cors_allowed_origins="*",
                   async_mode='eventlet',
                   logger=True,
                   engineio_logger=True)

# Konfigurasi dari Environment Variables
key = os.environ.get('ASCON_KEY', 'asconciphertest1').encode('utf-8')
nonce = os.environ.get('ASCON_NONCE', 'asconcipher1test').encode('utf-8')
associateddata = os.environ.get('ASCON_AD', 'ASCON').encode('utf-8')
variant = os.environ.get('ASCON_VARIANT', 'Ascon-128')

# MQTT Configuration
MQTT_BROKER = os.environ.get('MQTT_BROKER', 'broker.hivemq.com')
MQTT_PORT = int(os.environ.get('MQTT_PORT', 1883))
MQTT_TOPIC = os.environ.get('MQTT_TOPIC', 'soil-ascon128')

# Store data terakhir
last_data = {
    'moisture': 0,
    'sensor': 'soil_moisture',
    'unit': '%',
    'encrypted': '',
    'timestamp': None,
    'message_count': 0
}

def on_mqtt_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info(f"✅ Connected to MQTT broker: {MQTT_BROKER}")
        client.subscribe(MQTT_TOPIC)
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
            
            # Kirim ke semua client frontend
            socketio.emit('sensor_data', last_data)
            logger.info("📤 Sent to frontend via Socket.IO")
            
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
        'service': 'soil-moisture-monitor'
    }

@app.route('/api/data')
def api_data():
    return {
        'moisture': last_data['moisture'],
        'sensor': last_data['sensor'],
        'unit': last_data['unit'],
        'timestamp': last_data['timestamp'],
        'message_count': last_data['message_count']
    }

@socketio.on('connect')
def handle_connect():
    logger.info('✅ Client connected to Socket.IO')
    # Kirim data terakhir ke client baru
    socketio.emit('sensor_data', last_data)

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('❌ Client disconnected from Socket.IO')

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
    logger.info(f"🚀 Starting production server on port {port}")
    socketio.run(app, 
                 host='0.0.0.0', 
                 port=port, 
                 debug=False, 
                 allow_unsafe_werkzeug=True)