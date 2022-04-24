from json import loads
from typing import Callable, Coroutine

from aiohttp_sse_client.client import EventSource

ENDPOINT = "https://alerts.com.ua/api"


class API:
    def __init__(self, key):
        self.headers = {"X-API-Key": key}
        self.source = EventSource(
            ENDPOINT + "/states/live", headers=self.headers, timeout=0
        )

    async def listen(self, callback: Callable[[dict], Coroutine]):
        source = self.source
        while True:
            try:
                await source.connect()
                async for message in source:
                    if message.type != "ping":
                        print(message)
                    if message.type == "update":
                        await callback(loads(message.data)["state"])
            except Exception as e:
                print(e)
