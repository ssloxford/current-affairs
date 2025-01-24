from __future__ import annotations

from typing import Dict, NamedTuple, Tuple, List
import xml.etree.ElementTree as ET

from ..interface.socket_wrapper import V2GPacket
from .exi_interface import EXI_INSTANCE_APP, ExiException
from enum import Enum
from . import app_protocol
from ..utils.data_saver import DataSaver

class AppProtocolCode(Enum):
    OK = 0
    OKMinor = 1
    Failed = 2
    Invalid = 3


class SupportedAppProtocolEV():
    request: ET.Element
    request_inner: ET.Element
    protocols: Dict[int, app_protocol.AppProtocol]
    name: str

    def __init__(self, name: str, init_protos: List[Tuple[app_protocol.AppProtocol, int, int]]):
        self.request = ET.fromstring("""<?xml version="1.0" encoding="UTF-8"?>\
            <ns4:supportedAppProtocolReq xmlns:ns4="urn:iso:15118:2:2010:AppProtocol" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:ns3="http://www.w3.org/2001/XMLSchema">\
            </ns4:supportedAppProtocolReq>""")
        
        self.request_inner = self.request
        self.protocols = {}
        self.name = name

        for init in init_protos:
            self.add_proto(init[0], init[1], init[2])

    def add_proto(self, proto: app_protocol.AppProtocol, id: int, prio: int):
        res = ET.SubElement(self.request_inner, "AppProtocol")
        ET.SubElement(res, "ProtocolNamespace").text = proto.ns
        ET.SubElement(res, "VersionNumberMajor").text = str(proto.major)
        ET.SubElement(res, "VersionNumberMinor").text = str(proto.minor)
        ET.SubElement(res, "SchemaID").text = str(id)
        ET.SubElement(res, "Priority").text = str(prio)

        self.protocols[id] = proto

    async def encode(self) -> V2GPacket:
        return V2GPacket(1, 0x8001, await EXI_INSTANCE_APP.encode(self.request))

    async def decode(self, logger: DataSaver, packet: V2GPacket) -> Tuple[AppProtocolCode, app_protocol.AppProtocol | int | None]:
        with logger.trace_enter("supportedAppProtocolRes"):
            logger.log_entry("RAW", {
                "version": packet.version,
                "type": packet.type,
                "data": packet.data.hex(),
            })

            if packet.type != 0x8001:
                raise ExiException("Invalid type for supportedAppProtocolRes")
            
            parsed_str, parsed = await EXI_INSTANCE_APP.decode(packet.data)
            logger.log_entry("DECODED", parsed_str)
         
            if parsed.tag != "{urn:iso:15118:2:2010:AppProtocol}supportedAppProtocolRes":
                raise ExiException("Not supportedAppProtocolRes")
            
            code = parsed.find("ResponseCode")
            if code is None:
                raise ExiException("supportedAppProtocolRes missing ResponseCode")
            if code.text == "Failed_NoNegotiation":
                return (AppProtocolCode.Failed, None)

            chosen = parsed.find("SchemaID")

            if chosen is None or chosen.text is None:
                raise ExiException("supportedAppProtocolRes missing SchemaID")
            
            chosen_int = int(chosen.text)
            if chosen_int in self.protocols:
                chosen_proto = self.protocols[chosen_int]
                logger.log_entry("CHOSEN", {
                    "code": code.text,
                    "id": chosen_int,
                    "name": chosen_proto.short_name
                })
                if code.text == "OK_SuccessfulNegotiation":
                    return (AppProtocolCode.OK, chosen_proto)
                if code.text == "OK_SuccessfulNegotiationWithMinorDeviation":
                    return (AppProtocolCode.OKMinor, chosen_proto)
            else:
                logger.log_entry("CHOSEN", {
                    "code": code.text,
                    "id": chosen_int
                })
            
            return (AppProtocolCode.Invalid, chosen_int)
        
class AppProtocolRequestInfo(app_protocol.AppProtocolInfo):
    schema_id : int
    priority: int

    def __init__(self, ns: str, major: int, minor: int, schema_id: int, priority: int):
        super().__init__(ns, major, minor)    
    
        self.schema_id = schema_id
        self.priority = priority


PROTO_TESTS_EV = {
    "ALL": SupportedAppProtocolEV("ALL", [
        (app_protocol.V20DC, 0, 1),
        (app_protocol.V2V13, 1, 2),
        (app_protocol.V2V10, 2, 3),
        (app_protocol.DIN, 3, 4),
    ]),
    "MTLS": SupportedAppProtocolEV("MTLS", [
        (app_protocol.V20DC, 0, 1),
    ]),
    "UTLS": SupportedAppProtocolEV("UTLS", [
        (app_protocol.V2V13, 0, 1),
    ]),
    "NTLS": SupportedAppProtocolEV("NTLS", [
        (app_protocol.V2V13, 0, 1),
        (app_protocol.V2V10, 1, 2),
        (app_protocol.DIN, 2, 3),
    ]),
    "V20DC": SupportedAppProtocolEV("V20DC", [
        (app_protocol.V20DC, 0, 1)
    ]),
    "V2V13": SupportedAppProtocolEV("V2V13", [
        (app_protocol.V2V13, 0, 1)
    ]),
    "V2V10": SupportedAppProtocolEV("V2V10", [
        (app_protocol.V2V10, 0, 1)
    ]),
    "DIN": SupportedAppProtocolEV("DIN", [
        (app_protocol.DIN, 0, 1)
    ]),
}
