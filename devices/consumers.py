from channels.generic.websocket import AsyncWebsocketConsumer
import json


class MqttConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.deviceid = self.scope["url_route"]["kwargs"]["deviceid"]
        self.group_name = f"mqtt_{self.deviceid}"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def mqtt_message(self, event):
        await self.send(text_data=json.dumps({
            "deviceid": event["deviceid"],
            "data": event["message"]
        }))
