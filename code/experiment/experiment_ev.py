from __future__ import annotations
from abc import abstractmethod
import socket
from typing import Any, List, Tuple

from code.interface.socket_wrapper import WrappedSocket
from code.interface.trusted_ca_keys import TrustedCAKey

from ..v2g.app_protocol import AppProtocol
from ..v2g.supported_app_protocol import SupportedAppProtocolEV, AppProtocolCode
#from ..network.states import StateTask, TaskResultEnum, TaskRequirement
from ..network.states_task import StateTask, TaskResultEnum, TaskRequirement
from .. import controller
from .. import controller_ev
from ..network import ui_link_inner as ui_link
import asyncio
from ..interface import connection_ev
class Task_EV_SLAC(StateTask):

    def __init__(self, ui: ui_link.UI_Inner):
        super().__init__(ui, "SLAC", None)

    async def _run(self, ctrl: "controller_ev.ControllerEV") -> TaskResultEnum:
        with ctrl.logger.trace_enter(self.name):
            await asyncio.gather(ctrl.do_reset(), ctrl.do_slac_prepare())
            await ctrl.do_plug()
            await ctrl.do_slac()
        return TaskResultEnum.Success


TLS_BOOL_NAMES = ["NTLS", "YTLS"]
class Task_EV_SDP(StateTask):
    tls: bool

    def __init__(self, ui: ui_link.UI_Inner, task_slac: Task_EV_SLAC, tls: bool):
        super().__init__(ui, "SDP_" + TLS_BOOL_NAMES[tls], TaskRequirement(task_slac))
        self.tls = tls

    async def _run(self, ctrl: "controller_ev.ControllerEV") -> TaskResultEnum:
        with ctrl.logger.trace_enter(self.name):
            sdp = await ctrl.do_sdp(self.tls)
            if sdp.res is None:
                return TaskResultEnum.Failed_Anomaly
            if sdp.res.tls != self.tls:
                return TaskResultEnum.Failed
        return TaskResultEnum.Success

class Task_EV_Conn_Base(StateTask):
    tls: bool
    sub_name: str

    def __init__(self, ui: ui_link.UI_Inner, name: str, tls: bool, task_sdp: Task_EV_SDP):
        super().__init__(ui, "CONN_" + name, TaskRequirement(task_sdp))
        self.tls = tls
        self.sub_name = name

    @abstractmethod
    async def _do(self, ctrl: "controller_ev.ControllerEV") -> Tuple[WrappedSocket | None, TaskResultEnum]:
        pass

    async def _run(self, ctrl: "controller_ev.ControllerEV") -> TaskResultEnum:
        with ctrl.logger.trace_enter(self.name):
            sock, res = await self._do(ctrl)

            ctrl.sock = sock
        return res

class Task_EV_Conn_NTLS(Task_EV_Conn_Base):
    def __init__(self, ui: ui_link.UI_Inner, task_sdp: Task_EV_SDP):
        super().__init__(ui, "NTLS", False, task_sdp)

    async def _do(self, ctrl: "controller_ev.ControllerEV") -> Tuple[WrappedSocket | None, TaskResultEnum]:
        if ctrl.sdp is None or ctrl.sdp.res is None or ctrl.sdp.res.ip is None or ctrl.sdp.res.port is None:
            raise ValueError("No valid SDP before connect")
        if ctrl.sdp.res.tls != self.tls:
            raise ValueError("SDP TLS Mistmatch")

        sock = await connection_ev.create_ntls(
            ctrl.logger, ctrl.interface, ctrl.sdp.res.ip, ctrl.sdp.res.port
        )

        return sock, TaskResultEnum.Success

class Task_EV_Conn_V2(Task_EV_Conn_Base):
    trusted: List["TrustedCAKey"]

    def __init__(self, ui: ui_link.UI_Inner, task_sdp: Task_EV_SDP):
        super().__init__(ui, "UTLS_V2", True, task_sdp)

        self.trusted = []

    async def _do(self, ctrl: "controller_ev.ControllerEV") -> Tuple[WrappedSocket | None, TaskResultEnum]:
        if ctrl.sdp is None or ctrl.sdp.res is None or ctrl.sdp.res.ip is None or ctrl.sdp.res.port is None:
            raise ValueError("No valid SDP before connect")
        if ctrl.sdp.res.tls != self.tls:
            raise ValueError("SDP TLS Mistmatch")

        sock = await connection_ev.create_tls_dash2(
            ctrl.logger, ctrl.interface, ctrl.sdp.res.ip, ctrl.sdp.res.port,
            self.trusted
        )

        return sock, TaskResultEnum.Success
    

class Task_EV_Conn_TLS_Old(Task_EV_Conn_Base):
    trusted: List["TrustedCAKey"]

    def __init__(self, ui: ui_link.UI_Inner, task_sdp: Task_EV_SDP):
        super().__init__(ui, "OLD_TLS", True, task_sdp)

        self.trusted = []

    async def _do(self, ctrl: "controller_ev.ControllerEV") -> Tuple[WrappedSocket | None, TaskResultEnum]:
        if ctrl.sdp is None or ctrl.sdp.res is None or ctrl.sdp.res.ip is None or ctrl.sdp.res.port is None:
            raise ValueError("No valid SDP before connect")
        if ctrl.sdp.res.tls != self.tls:
            raise ValueError("SDP TLS Mistmatch")

        sock = await connection_ev.create_tls_old(
            ctrl.logger, ctrl.interface, ctrl.sdp.res.ip, ctrl.sdp.res.port,
            self.trusted
        )

        return sock, TaskResultEnum.Success
    
class Task_EV_Conn_V2_BadTrusted(Task_EV_Conn_Base):
    trusted: List["TrustedCAKey"]

    def __init__(self, ui: ui_link.UI_Inner, task_sdp: Task_EV_SDP):
        super().__init__(ui, "BAD_TRUSTED", True, task_sdp)

    async def _do(self, ctrl: "controller_ev.ControllerEV") -> Tuple[WrappedSocket | None, TaskResultEnum]:
        if ctrl.sdp is None or ctrl.sdp.res is None or ctrl.sdp.res.ip is None or ctrl.sdp.res.port is None:
            raise ValueError("No valid SDP before connect")
        if ctrl.sdp.res.tls != self.tls:
            raise ValueError("SDP TLS Mistmatch")

        sock = await connection_ev.create_tls_dash2_bad_trusted(
            ctrl.logger, ctrl.interface, ctrl.sdp.res.ip, ctrl.sdp.res.port,
        )

        return sock, TaskResultEnum.Success

class Task_EV_Conn_V2_Suite(Task_EV_Conn_Base):
    trusted: List["TrustedCAKey"]
    suites: List["str"]

    def __init__(self, ui: ui_link.UI_Inner, name: str, task_sdp: Task_EV_SDP):
        super().__init__(ui, "TLS12_" + name, True, task_sdp)

        self.trusted = []
        self.suites = []

    async def _do(self, ctrl: "controller_ev.ControllerEV") -> Tuple[WrappedSocket | None, TaskResultEnum]:
        if ctrl.sdp is None or ctrl.sdp.res is None or ctrl.sdp.res.ip is None or ctrl.sdp.res.port is None:
            raise ValueError("No valid SDP before connect")
        if ctrl.sdp.res.tls != self.tls:
            raise ValueError("SDP TLS Mistmatch")

        sock = await connection_ev.create_tls_dash2_suite(
            ctrl.logger, ctrl.interface, ctrl.sdp.res.ip, ctrl.sdp.res.port,
            self.trusted,
            self.suites
        )

        return sock, TaskResultEnum.Success
    
class Task_EV_Conn_V20(Task_EV_Conn_Base):
    cert: Any
    trusted: List["TrustedCAKey"]

    def __init__(self, ui: ui_link.UI_Inner, task_sdp: Task_EV_SDP):
        super().__init__(ui, "MTLS_V20", True, task_sdp)

        self.cert = None
        self.trusted = []

    async def _do(self, ctrl: "controller_ev.ControllerEV") -> Tuple[WrappedSocket | None, TaskResultEnum]:
        if ctrl.sdp is None or ctrl.sdp.res is None or ctrl.sdp.res.ip is None or ctrl.sdp.res.port is None:
            raise ValueError("No valid SDP before connect")
        if ctrl.sdp.res.tls != self.tls:
            raise ValueError("SDP TLS Mistmatch")

        sock = await connection_ev.create_tls_dash20(
            ctrl.logger, ctrl.interface, ctrl.sdp.res.ip, ctrl.sdp.res.port,
            self.cert
        )

        return sock, TaskResultEnum.Success
class Task_EV_Supported(StateTask):
    exp_con: Task_EV_Conn_Base

    supported: SupportedAppProtocolEV
    selected: None | AppProtocol

    def __init__(self, ui: ui_link.UI_Inner, exp_con: Task_EV_Conn_Base, supported: SupportedAppProtocolEV):
        super().__init__(ui, "SUPPORTED_" + exp_con.sub_name + "_" + supported.name, TaskRequirement(exp_con))
        self.exp_con = exp_con
        self.supported = supported

    async def _run(self, ctrl: "controller_ev.ControllerEV") -> TaskResultEnum:
        with ctrl.logger.trace_enter(self.name):
            if ctrl.sock is None:
                raise ValueError("No socket when running selected")
            await ctrl.sock.send_v2g_packet(await self.supported.encode())
            selected = await self.supported.decode(ctrl.logger, await ctrl.sock.read_v2g_packet())
            if (selected[0] == AppProtocolCode.OK) or (selected[0] == AppProtocolCode.OKMinor):
                self.selected = selected[1]#type: ignore
                return TaskResultEnum.Success
            return TaskResultEnum.Failed

class Task_EV_V2G(StateTask):
    exp_sup: Task_EV_Supported

    def __init__(self, ui: ui_link.UI_Inner, exp_sup: Task_EV_Supported):
        super().__init__(ui, "V2G_" + exp_sup.exp_con.sub_name + "_" + exp_sup.supported.name, TaskRequirement(exp_sup))
        self.exp_sup = exp_sup

    async def _run(self, ctrl: "controller.Controller") -> TaskResultEnum:
        with ctrl.logger.trace_enter(self.name):
            if ctrl.sock is None:
                raise ValueError("No socket when running V2G")
            if self.exp_sup.selected is None:
                raise ValueError("No selected protocol when running V2G")
            await self.exp_sup.selected.ev_run_query_experiment(ctrl.logger, ctrl.sock, ctrl.mac)
            return TaskResultEnum.Success