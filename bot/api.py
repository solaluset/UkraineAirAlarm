import logging
from json import loads
from typing import Callable, Coroutine

import requests
from aiohttp_sse_client.client import EventSource


BASE_URL = "https://alerts.com.ua"
ENDPOINT = BASE_URL + "/api"


class API:
    def __init__(self, key):
        self.headers = {"X-API-Key": key}

    async def listen(self, callback: Callable[[dict], Coroutine]):
        source = EventSource(
            ENDPOINT + "/states/live", headers=self.headers, timeout=0
        )
        while True:
            try:
                await source.connect()
                async for message in source:
                    if message.type != "ping":
                        logging.info(message)
                    if message.type == "update":
                        await callback(loads(message.data)["state"])
            except Exception as e:
                logging.error(e)

    def get_regions(self) -> dict[str, int]:
        return {
            s["name"]: s["id"]
            for s in requests.get(ENDPOINT + "/states", headers=self.headers).json()[
                "states"
            ]
        }
