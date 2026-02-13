import json
import threading
import paho.mqtt.client as mqtt
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from decouple import config

MQTT_BROKER = config('MQTT_BROKER')
MQTT_PORT = config('MQTT_PORT', cast=int)
MQTT_USER = config('MQTT_USER')
MQTT_PASSWORD = config('MQTT_PASSWORD')
MQTT_TOPIC = config('MQTT_TOPIC')  

client = mqtt.Client()


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ MQTT Connected")
        client.subscribe(MQTT_TOPIC)
    else:
        print("❌ MQTT Connection Failed:", rc)


def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)

        deviceid = data.get("deviceID")
        if not deviceid:
            return

        channel_layer = get_channel_layer()

        async_to_sync(channel_layer.group_send)(
            f"mqtt_{deviceid}",
            {
                "type": "mqtt_message",
                "deviceid": deviceid,
                "message": data,
            }
        )

    except Exception as e:
        print("MQTT message error:", e)



def start_mqtt():
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT)

    thread = threading.Thread(target=client.loop_forever)
    thread.daemon = True
    thread.start()

    print("🚀 MQTT Client Started")
