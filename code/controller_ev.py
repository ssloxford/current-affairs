from __future__ import annotations
from abc import ABC, abstractmethod
from calendar import day_abbr
import os
from typing import Any, List

#import v2g.protocol_version as protocol_version
from .interface import slac
from .interface import sdp
from .interface import connection_ev
from .interface import socket_wrapper
from .interface import hal
from . import controller
from . import pcap_wrapper

import asyncio

#
# Controller base class
#
class ControllerEV(controller.Controller):
    hardware: hal.Module_EV

    sdp: sdp.SDPRequest | None

    def __init__(self, interface: str, args):
        super().__init__(interface, args)
        slac.ev_init(interface)

        self.hardware = hal.Module_EV()

        self.sdp = None
        self.sock = None

    async def on_slac_status(self, progress: slac.SlacProgress, done: bool):
        print(f"SLAC status: {progress.name} {done}")
        await self.ui.state_slac.set_state(progress, done)

    #Running functions

    async def do_reset(self):
        self.hardware.unplug()

        if self.sock is not None:
            self.sock.close()
        self.sock = None

    async def do_plug(self):
        #Wait till user decides to start
        await self.wait_should_enable()
        #Connect car
        self.hardware.plug_sniff()

        await self.basic_signalling.wait_ev_charger_connected(None)

        self.hardware.plug_connect()
        
        await self.basic_signalling.wait_ev_charger_ready(None)

    async def do_slac_prepare(self):
        await slac.ev_prepare(self.logger, self.on_slac_status)

    async def do_slac(self) -> slac.SlacResult:
        #Execute SLAC
        slac_res = await slac.ev_run(self.logger, self.on_slac_status)

        return slac_res

    async def do_sdp(self, tls: bool) -> sdp.SDPRequest:
        self.sdp = await sdp.sdp_client(self.logger, self.interface, tls)
        return self.sdp

    async def do_connection(self, version: int, cert: Any) -> socket_wrapper.WrappedSocket:
        if self.sdp is None or self.sdp.res is None or self.sdp.res.ip is None or self.sdp.res.port is None:
            raise ValueError("No valid SDP before connect")
        if version == 0:
            if self.sdp.res.tls:
                raise ValueError("TLS SDP before NTLS connect")
            ntls_sock = await connection_ev.create_ntls(self.logger, self.interface, self.sdp.res.ip, self.sdp.res.port)

            self.sock = ntls_sock
            return ntls_sock
        elif version == 1:
            if not self.sdp.res.tls:
                raise ValueError("NTLS SDP before TLS connect")
            utls_sock = await connection_ev.create_tls_dash2(self.logger, self.interface, self.sdp.res.ip, self.sdp.res.port, [])
            
            self.sock = utls_sock
            return utls_sock
        elif version == 2:
            if not self.sdp.res.tls:
                raise ValueError("NTLS SDP before TLS connect")
            mtls_sock = await connection_ev.create_tls_dash20(self.logger, self.interface, self.sdp.res.ip, self.sdp.res.port, cert)

            self.sock = mtls_sock
            return mtls_sock
        raise ValueError("Invalid type")
