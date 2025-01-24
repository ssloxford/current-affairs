"""
Implementation of the CCS App Protocol messages
"""

from __future__ import annotations
from abc import abstractmethod
from struct import pack

from typing import Dict, NamedTuple, Tuple, List
import xml.etree.ElementTree as ET

from .exi_interface import EXI_INSTANCE_APP, EXI_INSTANCE_DIN, EXI_INSTANCE_V20AC, EXI_INSTANCE_V20ACDP, EXI_INSTANCE_V20CM, EXI_INSTANCE_V20WPT, EXI_INSTANCE_V2V10, EXI_INSTANCE_V2V13, EXI_INSTANCE_V20DC, ExiException, ExiInterface
from enum import Enum
import time
from ..utils.data_saver import DataSaver
from ..interface.socket_wrapper import V2GPacket, WrappedSocket

"""
Information about AppProtocols needed for version negotiation
"""
class AppProtocolInfo():
    ns: str
    major: int
    minor: int

    def __init__(self, ns: str, major: int, minor: int):
        self.ns = ns
        self.major = major
        self.minor = minor

class AppProtocol(AppProtocolInfo):
    """Base class for testing app protocols"""
    short_name: str

    def __init__(self, short_name: str, ns: str, major: int, minor: int):
        super().__init__(ns, major, minor)

        self.short_name = short_name

    @abstractmethod
    async def ev_run_query_experiment(self, logger: DataSaver, sock: WrappedSocket, mac: bytes):
        pass

class AppProtocolA(AppProtocol):
    """Common code for DIN and ISO 15118-2"""

    exi: ExiInterface

    ns_mapping: Dict[str, str]

    session_id: bytes

    def __init__(self, short_name, major, minor, exi, ns, ns_mapping):
        super().__init__(
            short_name=short_name, major=major, minor=minor, ns=ns)

        self.exi = exi
        self.ns_mapping = ns_mapping

        self.session_id = b'\x00'

    def create_packet(self) -> Tuple[ET.Element, ET.Element]:
        """Create packet structure ready to be filled"""

        req = ET.fromstring(f"""<?xml version="1.0" encoding="UTF-8"?>
            <v2gci_d:V2G_Message
            xmlns:v2gci_b="{self.ns_mapping['v2gci_b']}"
            xmlns:xmlsig="http://www.w3.org/2000/09/xmldsig#"
            xmlns:v2gci_d="{self.ns_mapping['v2gci_d']}"
            xmlns:v2gci_t="{self.ns_mapping['v2gci_t']}"
            xmlns:v2gci_h="{self.ns_mapping['v2gci_h']}"
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
                <v2gci_d:Header>
                    <v2gci_h:SessionID></v2gci_h:SessionID>
                </v2gci_d:Header>
                <v2gci_d:Body>
                </v2gci_d:Body>
            </v2gci_d:V2G_Message>""")
        
        # Set session ID field
        session_id = req.find(f"{{{self.ns_mapping['v2gci_d']}}}Header/{{{self.ns_mapping['v2gci_h']}}}SessionID")
        if session_id is None:
            raise ValueError("Did not find session_id in new packet")
        session_id.text = self.session_id.hex()

        # Return container for the body
        body = req.find(f"{{{self.ns_mapping['v2gci_d']}}}Body")
        if body is None:
            raise ValueError("Did not find body in new packet")
        return (req, body)

    async def decode(self, logger: DataSaver, packet: V2GPacket, packet_type: str) -> Tuple[ET.Element, bytes, ET.Element]:
        """Decode received packet"""

        logger.log_entry("RAW", {
            "version": packet.version,
            "type": packet.type,
            "data": packet.data.hex(),
        })
        
        if packet.type != 0x8001:
            raise ExiException("Invalid type for " + packet_type)
        
        parsed_str, parsed = await self.exi.decode(packet.data)
        logger.log_entry("DECODED", parsed_str)

        if parsed.tag != f"{{{self.ns_mapping['v2gci_d']}}}V2G_Message":
            raise ExiException("Invalid root tag")

        response_sessionid = parsed.find(f"{{{self.ns_mapping['v2gci_d']}}}Header/{{{self.ns_mapping['v2gci_h']}}}SessionID")
        if response_sessionid is None or response_sessionid.text is None:
            raise ExiException("No Session ID")
        session_id = bytes.fromhex(response_sessionid.text)

        response_body = parsed.find(f"{{{self.ns_mapping['v2gci_d']}}}Body/{{{self.ns_mapping['v2gci_b']}}}{packet_type}")
        if response_body is None:
            raise ExiException(f"Not {packet_type}")

        return parsed, session_id, response_body


    async def ev_session_setup_req(self, evcc_id) -> V2GPacket :
        self.session_id = b'\x00'
        base_elem, body = self.create_packet()

        request_body = ET.SubElement(body, f"{{{self.ns_mapping['v2gci_b']}}}SessionSetupReq")

        ET.SubElement(
            request_body,
            f"{{{self.ns_mapping['v2gci_b']}}}EVCCID"
        ).text=str(evcc_id)

        return V2GPacket(1, 0x8001, await self.exi.encode(base_elem))

    async def ev_session_setup_res(self, logger: DataSaver, packet: V2GPacket):
        with logger.trace_enter("SessionSetupRes"):
            parsed, session_id, response_body = await self.decode(logger, packet, "SessionSetupRes")
            logger.log_entry("SESSION_ID", session_id.hex())
            self.session_id = session_id

            respose_code = response_body.find(f"{{{self.ns_mapping['v2gci_b']}}}ResponseCode")
            if respose_code is None:
                raise ExiException("SessionSetupRes missing ResponseCode")
            if (respose_code.text != "OK_NewSessionEstablished") and (respose_code.text != "OK"):
                raise ExiException("SessionSetupRes failed")

            response_evse = response_body.find(f"{{{self.ns_mapping['v2gci_b']}}}EVSEID")
            response_timestamp = response_body.find(f"{{{self.ns_mapping['v2gci_b']}}}EVSETimeStamp") #-2:2013
            response_datetime = response_body.find(f"{{{self.ns_mapping['v2gci_b']}}}DateTimeNow")# DIN, -2:2010

            logger.log_entry("RESULT", {
                "EVSEID": response_evse.text if response_evse is not None else None,
                "EVSETimeStamp": response_timestamp.text if response_timestamp is not None else None,
                "DateTimeNow": response_datetime.text if response_datetime is not None else None,
            })

    async def ev_service_discovery_req(self):
        base_elem, body = self.create_packet()

        request_body = ET.SubElement(body, f"{{{self.ns_mapping['v2gci_b']}}}ServiceDiscoveryReq")

        return V2GPacket(1, 0x8001, await self.exi.encode(base_elem))

    async def ev_service_discovery_res(self, logger: DataSaver, packet: V2GPacket):
        with logger.trace_enter("ServiceDiscoveryRes"):
            parsed, session_id, response_body = await self.decode(logger, packet, "ServiceDiscoveryRes")

    async def ev_session_stop_req(self):
        base_elem, body = self.create_packet()

        response_body = ET.SubElement(body, f"{{{self.ns_mapping['v2gci_b']}}}SessionStopReq")

        if self.short_name == "V2V13":
            ET.SubElement(
                response_body, f"{{{self.ns_mapping['v2gci_b']}}}ChargingSession"
            ).text = "Terminate"

        return V2GPacket(1, 0x8001, await self.exi.encode(base_elem))

    async def ev_session_stop_res(self, logger: DataSaver, packet: V2GPacket):
        with logger.trace_enter("SessionStopRes"):
            parsed, session_id, response_body = await self.decode(logger, packet, "SessionStopRes")

    async def ev_run_query_experiment(self, logger: DataSaver, sock: WrappedSocket, mac: bytes):
        self.session_id = b'\x00'

        await sock.send_v2g_packet(await self.ev_session_setup_req(mac.hex()))
        await self.ev_session_setup_res(logger, await sock.read_v2g_packet())

        await sock.send_v2g_packet(await self.ev_service_discovery_req())
        await self.ev_service_discovery_res(logger, await sock.read_v2g_packet())

        await sock.send_v2g_packet(await self.ev_session_stop_req())
        await self.ev_session_stop_res(logger, await sock.read_v2g_packet())



class AppProtocolDIN(AppProtocolA):
    def __init__(self):
        super().__init__(
            short_name="DIN",
            ns = "urn:din:70121:2012:MsgDef",
            major=2, minor=0,
            exi=EXI_INSTANCE_DIN,
            ns_mapping = {
                "v2gci_d": "urn:din:70121:2012:MsgDef",
                "v2gci_t": "urn:din:70121:2012:MsgDataTypes",
                "v2gci_h": "urn:din:70121:2012:MsgHeader",
                "v2gci_b": "urn:din:70121:2012:MsgBody"
            }
        )
        
class AppProtocolV2V10(AppProtocolA):
    def __init__(self):
        super().__init__(
            short_name="V2V10",
            ns = "urn:iso:15118:2:2010:MsgDef",
            major=1, minor=0,
            exi=EXI_INSTANCE_V2V10,
            ns_mapping = {
                "v2gci_d": "urn:iso:15118:2:2010:MsgDef",
                "v2gci_t": "urn:iso:15118:2:2010:MsgDataTypes",
                "v2gci_h": "urn:iso:15118:2:2010:MsgHeader",
                "v2gci_b": "urn:iso:15118:2:2010:MsgBody"
            }
        )

class AppProtocolV2V13(AppProtocolA):
    def __init__(self):
        super().__init__(
            short_name="V2V13",
            ns = "urn:iso:15118:2:2013:MsgDef",
            major=2, minor=0,
            exi=EXI_INSTANCE_V2V13,
            ns_mapping = {
                "v2gci_d": "urn:iso:15118:2:2013:MsgDef",
                "v2gci_t": "urn:iso:15118:2:2013:MsgDataTypes",
                "v2gci_h": "urn:iso:15118:2:2013:MsgHeader",
                "v2gci_b": "urn:iso:15118:2:2013:MsgBody"
            }
        )

class AppProtocolV20Base(AppProtocol):
    def __init__(self, short_name, major, minor, ns):
        super().__init__(
            short_name=short_name, major=major, minor=minor, ns = ns)
        
    async def encode(self, xml_obj: ET.Element, proto: int) -> V2GPacket:
        if proto == 0x8002:
            return V2GPacket(1, proto, await EXI_INSTANCE_V20CM.encode(xml_obj))
        elif proto == 0x8003:
            return V2GPacket(1, proto, await EXI_INSTANCE_V20AC.encode(xml_obj))
        elif proto == 0x8004:
            return V2GPacket(1, proto, await EXI_INSTANCE_V20DC.encode(xml_obj))
        elif proto == 0x8005:
            return V2GPacket(1, proto, await EXI_INSTANCE_V20ACDP.encode(xml_obj))
        elif proto == 0x8006:
            return V2GPacket(1, proto, await EXI_INSTANCE_V20WPT.encode(xml_obj))
        raise ValueError("Invalid protocol ID")

    async def decode(self, packet: V2GPacket) -> Tuple[str, ET.Element]:
        if packet.version != 1:
            raise ValueError("Invalid protocol version")
        if packet.type == 0x8002:
            return await EXI_INSTANCE_V20CM.decode(packet.data)
        elif packet.type == 0x8003:
            return await EXI_INSTANCE_V20AC.decode(packet.data)
        elif packet.type == 0x8004:
            return await EXI_INSTANCE_V20DC.decode(packet.data)
        elif packet.type == 0x8005:
            return await EXI_INSTANCE_V20ACDP.decode(packet.data)
        elif packet.type == 0x8006:
            return await EXI_INSTANCE_V20WPT.decode(packet.data)
        raise ValueError("Invalid protocol ID")

DIN = AppProtocolDIN()
V2V10 = AppProtocolV2V10()
V2V13 = AppProtocolV2V13()
V20AC = AppProtocolV20Base(short_name="V20AC", ns="urn:iso:std:iso:15118:-20:AC", major=1, minor=0)
V20DC = AppProtocolV20Base(short_name="V20DC", ns="urn:iso:std:iso:15118:-20:DC", major=1, minor=0)
V20ACDP = AppProtocolV20Base(short_name="V20ACDP", ns="urn:iso:std:iso:15118:-20:ACDP", major=1, minor=0)
V20WPT = AppProtocolV20Base(short_name="V20WPT", ns="urn:iso:std:iso:15118:-20:WPT", major=1, minor=0)
