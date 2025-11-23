# Subscriber.py (Untuk Soil Moisture Sensor - Fixed)
import paho.mqtt.client as mqtt
import json
import binascii
import time
import sys

# Cek keberadaan ascon.py
try:
    import ascon 
except ImportError:
    print("Error: File 'ascon.py' tidak ditemukan di folder ini!")
    sys.exit(1)

# --- KONFIGURASI ---
MQTT_CLIENT_ID = "pc-soil-subscriber-001" 
MQTT_BROKER    = "broker.hivemq.com"
MQTT_USER      = ""
MQTT_PASSWORD  = ""
MQTT_TOPIC     = "soil-ascon128"

# Key & Nonce (Harus sama persis dengan ESP32)
# Catatan: Key dan nonce ini harus sama dengan yang di-hardcode di ascon.py
key   = b"asconciphertest1"      # 16 bytes
nonce = b"asconcipher1test"      # 16 bytes  
associateddata = b"ASCON"
variant = "Ascon-128"

def check_ascon_function():
    """Cek signature fungsi di ascon.py"""
    print("🔍 Memeriksa fungsi ASCON yang tersedia...")
    
    # Cek fungsi apa saja yang ada
    available_functions = [func for func in dir(ascon) if callable(getattr(ascon, func))]
    print(f"📋 Fungsi yang tersedia: {available_functions}")
    
    # Cek signature demo_aead_p jika ada
    if hasattr(ascon, 'demo_aead_p'):
        import inspect
        try:
            sig = inspect.signature(ascon.demo_aead_p)
            print(f"📝 Signature demo_aead_p: {sig}")
        except:
            print("📝 Tidak bisa mendapatkan signature demo_aead_p")
    
    print()

# Callback saat terkoneksi
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"✅ Berhasil connect ke Broker! (Return Code: {rc})")
        client.subscribe(MQTT_TOPIC)
        print(f"🎯 Mendengarkan topik: {MQTT_TOPIC}")
        print("⏳ Menunggu data soil moisture...")
    else:
        print(f"❌ Gagal connect, return code: {rc}")

# Callback saat pesan diterima
def on_message(client, userdata, msg):
    try:
        print("\n" + "="*50)
        print(f"📨 Pesan masuk dari topik: {msg.topic}")
        
        payload_str = msg.payload.decode('utf-8')
        print(f"📄 Raw JSON: {payload_str}")
        
        # Parse JSON payload
        data = json.loads(payload_str)
        encrypted_hex = data['data']
        sensor_type = data.get('sensor', 'unknown')
        unit = data.get('unit', '%')
        
        print(f"🔐 Data Terenkripsi (Hex): {encrypted_hex}")
        print(f"📊 Sensor Type: {sensor_type}")
        print(f"📏 Unit: {unit}")
        print(f"🔢 Panjang Hex: {len(encrypted_hex)} karakter")

        # Konversi hex string ke bytes
        encrypted_bytes = binascii.unhexlify(encrypted_hex)
        
        print(f"🔍 Proses dekripsi dengan:")
        print(f"   Variant: {variant}")
        print(f"   Key (hardcoded di ascon.py): {key}")
        print(f"   Nonce (hardcoded di ascon.py): {nonce}")
        print(f"   Associated Data (hardcoded di ascon.py): {associateddata}")

        # Dekripsi dengan 2 parameter saja (sesuai signature)
        print("🔄 Melakukan dekripsi dengan 2 parameter...")
        decrypted_bytes = ascon.demo_aead_p(variant, encrypted_bytes)

        if decrypted_bytes:
            # Konversi bytes kembali ke integer
            moisture_value = int.from_bytes(decrypted_bytes, 'big')
            
            print(f"✅ Dekripsi Berhasil!")
            print(f"💧 Kelembaban Tanah: {moisture_value}%")
            
            # Logika status soil moisture
            if moisture_value < 20:
                print(">> 🚨 CRITICAL: TANAH SANGAT KERING! 🚨")
                print(">> 💦 Perlu penyiraman segera!")
            elif moisture_value < 40:
                print(">> ⚠️  WARNING: TANAH KERING")
                print(">> 💧 Pertimbangkan penyiraman")
            elif moisture_value < 70:
                print(">> ✅ Status Optimal")
                print(">> 🌱 Kondisi tanah baik")
            else:
                print(">> ⚠️  WARNING: TANAH TERLALU BASAH")
                print(">> 🛑 Kurangi penyiraman")
                
            # Tampilkan visual progress bar sederhana
            bars = moisture_value // 10
            progress = "[" + "█" * bars + " " * (10 - bars) + "]"
            print(f"📊 {progress} {moisture_value}%")
            
        else:
            print("❌ Gagal Dekripsi!")
            print("   Kemungkinan penyebab:")
            print("   - Key/Nonce di ascon.py tidak sesuai dengan ESP32")
            print("   - Data terkorupsi selama transmisi")

    except KeyError as e:
        print(f"❌ Error: Key '{e}' tidak ditemukan dalam JSON")
        print("   Pastikan format payload sesuai dengan publisher")
    except json.JSONDecodeError as e:
        print(f"❌ Error: Format JSON tidak valid - {e}")
    except binascii.Error as e:
        print(f"❌ Error: Format hex tidak valid - {e}")
    except Exception as e:
        print(f"❌ Error memproses pesan: {e}")
        import traceback
        traceback.print_exc()

def main():
    # Cek fungsi ASCON terlebih dahulu
    check_ascon_function()
    
    # --- SETUP CLIENT MQTT ---
    print("🔧 Menyiapkan MQTT Client...")
    print(f"📡 Broker: {MQTT_BROKER}")
    print(f"🎯 Topic: {MQTT_TOPIC}")
    print("ℹ️  Key, Nonce, dan Associated Data di-hardcode di ascon.py")

    try:
        # Coba menggunakan Paho MQTT v2.x
        from paho.mqtt.enums import CallbackAPIVersion
        client = mqtt.Client(CallbackAPIVersion.VERSION2, MQTT_CLIENT_ID)
        print("🔍 Menggunakan Paho MQTT v2.x")
    except ImportError:
        # Fallback ke Paho MQTT v1.x
        print("🔍 Menggunakan Paho MQTT v1.x")
        client = mqtt.Client(MQTT_CLIENT_ID)

    # Set credentials (jika ada)
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

    # Assign callback functions
    client.on_connect = on_connect
    client.on_message = on_message

    # Setup exception handling
    def on_disconnect(client, userdata, rc):
        if rc != 0:
            print("❌ Koneksi terputus secara tidak normal, mencoba reconnect...")
    
    client.on_disconnect = on_disconnect

    # Connect dan mulai loop
    try:
        print(f"🔄 Menghubungkan ke {MQTT_BROKER}...")
        client.connect(MQTT_BROKER, 1883, 60)
        
        print("🎉 Subscriber siap! Press Ctrl+C untuk berhenti.")
        print("="*50)
        
        # Loop forever
        client.loop_forever()
        
    except KeyboardInterrupt:
        print("\n🛑 Program dihentikan oleh user")
        client.disconnect()
    except Exception as e:
        print(f"❌ Gagal melakukan koneksi: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()