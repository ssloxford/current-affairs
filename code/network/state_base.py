from __future__ import annotations

from abc import abstractmethod
import asyncio
from typing import Any, Dict, List, TYPE_CHECKING, NamedTuple, Tuple

if TYPE_CHECKING:
    from . import ui_link

import random

class StateBaseClass:
    ws: ui_link.UI_Link
    def __init__(self, ws: "ui_link.UI_Link"):
        self.ws = ws

    @abstractmethod
    async def send_state_init(self, client):
        pass

class StateWaiter(StateBaseClass):
    type: str

    event: asyncio.Event
    waiting: bool
    waiting_cookie: int
    wait_result: str

    wait_delay: float

    auto_key: str | None

    def __init__(self, ws: "ui_link.UI_Link", type: str):
        super().__init__(ws)

        self.type = type

        self.event = asyncio.Event()
        self.waiting = False
        self.waiting_cookie = -1
        self.wait_result = ""

        self.wait_delay = 2

        self.auto_key = None

    async def get_state(self):
        return {
            "type": self.type,
            "waiting": self.waiting,
            "waiting_cookie": self.waiting_cookie,
            "auto_key": self.auto_key
        }

    async def send_state_update(self):
        await self.ws.send_broadcast(await self.get_state())

    async def send_state_init(self, client):
        await self.ws.send_client(client, await self.get_state())

    def schedule_auto_task(self):
        async def task(object: StateWaiter, waiting_cookie: int, wait_result: str):
            await asyncio.sleep(self.wait_delay)
            await object.on_click(waiting_cookie, wait_result)

        if self.auto_key is not None:
            asyncio.ensure_future(task(self, self.waiting_cookie, self.auto_key))

    async def wait_user(self) -> str:
        try:
            self.wait_result = ""
            self.waiting_cookie = int(random.random() * 1e6)
            self.waiting = True
            self.event.clear()
            await self.send_state_update()
            self.schedule_auto_task()

            await self.event.wait()
        finally:
            self.event.clear()
            self.waiting_cookie = -1
            self.waiting = False

        await self.send_state_update()

        return self.wait_result
            

    def cancel(self):
        if self.waiting:
            self.event.set()

    async def on_click(self, waiting_cookie: int, wait_result: str):
        if self.waiting and (waiting_cookie == self.waiting_cookie):
            self.wait_result = wait_result
            self.event.set()
        else:
            await self.send_state_update()

    async def on_change_auto(self, auto_key: str):
        self.auto_key = auto_key
        self.schedule_auto_task()

    async def on_message(self, message: Any):
        if message["type"] == "click":
            await self.on_click(message["cookie"], message["result"])
        if message["type"] == "auto":
            await self.on_change_auto(message["key"])
