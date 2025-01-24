from __future__ import annotations

from ..utils import settings

from .slac_common import *
if settings.SKIP_SLAC:
    from .slac_tst import *
else:
    from .slac_hw import *

from ..network.states import StateBaseClass
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..network import ui_link_inner as ui_link

    
class StateSLAC(StateBaseClass):
    state: SlacProgress
    state_done: bool

    result: SlacResult | None

    def __init__(self, ws: "ui_link.UI_Inner"):
        super().__init__(ws)

        self.state = SlacProgress.S00_NONE
        self.state_done = False

        self.result = None

    async def send_state_state(self):
        await self.ws.send_broadcast({
            "type": "SLAC_State",
            "state": self.state.value,
            "state_done": self.state_done
        })

    async def send_state_update(self):
        if self.result is None:
            return
        await self.ws.send_broadcast({
            "type": "SLAC_Result",
            "result": self.result.to_json()
        })

    async def send_state_init(self, client):
        await self.ws.send_client(client, {
            "type": "SLAC_State",
            "state": self.state.value,
            "state_done": self.state_done
        })
        if self.result is not None:
            await self.ws.send_client(client, {
                "type": "SLAC_Result",
                "result": self.result.to_json()
            })

    async def set_state(self, state, state_done):
        self.state = state
        self.state_done = state_done
        await self.send_state_state()

    async def set_response(self, result):
        self.result = result
        await self.send_state_update()

