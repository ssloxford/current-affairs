from __future__ import annotations

from asyncio import Lock, Event
from typing import Any

#Wrapper around asyncio.Event, in a way that also passes data
class DataEvent:
    ev: Event
    data: Any
    lock: Lock

    def __init__(self):
        self.ev = Event()
        self.data = None
        self.lock = Lock()

    async def set(self, data: Any):
        await self.lock.acquire()
        self.ev.set()
        self.data = data
        self.lock.release()

    #Only supports one thread using get functions
    async def try_get(self) -> Any | None:
        await self.lock.acquire()
        tmp = None
        if self.ev.is_set():
            self.ev.clear()
            tmp = self.data
        self.lock.release()
        return tmp

    async def wait_get(self) -> Any:
        await self.ev.wait()
        await self.lock.acquire()
        self.ev.clear()
        tmp = self.data
        self.lock.release()
        return tmp