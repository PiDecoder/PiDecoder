#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import ipaddress
import base64, hashlib, os, socket, uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote, urlparse
from urllib.error import HTTPError, URLError
from urllib.request import HTTPDigestAuthHandler, HTTPPasswordMgrWithDefaultRealm, Request, build_opener
from xml.etree import ElementTree as ET

SOAP='http://www.w3.org/2003/05/soap-envelope'
WSA='http://www.w3.org/2005/08/addressing'
WSD='http://schemas.xmlsoap.org/ws/2005/04/discovery'
WSSE='http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd'
WSU='http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd'
TDS='http://www.onvif.org/ver10/device/wsdl'
TRT='http://www.onvif.org/ver10/media/wsdl'
TT='http://www.onvif.org/ver10/schema'
TPTZ='http://www.onvif.org/ver20/ptz/wsdl'
NS={'s':SOAP,'wsa':WSA,'d':WSD,'tds':TDS,'trt':TRT,'tt':TT,'tptz':TPTZ}

@dataclass
class Credentials:
    username:str=''; password:str=''
class OnvifError(RuntimeError): pass

def _text(node,default=''):
    return node.text.strip() if node is not None and node.text else default

def _local(tag): return tag.rsplit('}',1)[-1]

def _scope_values(scopes):
    values={}
    for item in scopes.split():
        decoded=unquote(item)
        for key in ('name','hardware','location','Profile'):
            marker=f'/{key}/'
            if marker in decoded: values[key.lower()]=decoded.split(marker,1)[1].replace('/',' ')
    return values

def _ipv4_interfaces():
    import json
    import subprocess

    interfaces = []
    try:
        result = subprocess.run(
            ['ip', '-j', '-4', 'addr', 'show', 'up'],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        result = None

    if result is not None and result.returncode == 0:
        try:
            documents = json.loads(result.stdout)
        except json.JSONDecodeError:
            documents = []
        for document in documents:
            name = str(document.get('ifname', ''))
            if name == 'lo':
                continue
            for item in document.get('addr_info', []):
                if item.get('family') != 'inet':
                    continue
                address = str(item.get('local', ''))
                if not address or address.startswith('127.'):
                    continue
                interfaces.append({'name': name, 'address': address})

    if not interfaces:
        try:
            infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET, socket.SOCK_DGRAM)
        except socket.gaierror:
            infos = []
        seen = set()
        for info in infos:
            address = info[4][0]
            if address.startswith('127.') or address in seen:
                continue
            seen.add(address)
            interfaces.append({'name': 'auto', 'address': address})
    return interfaces


def _probe_xml(discovery_namespace, addressing_namespace, filtered):
    message_id = f"urn:uuid:{uuid.uuid4()}"

    destination = (
        "urn:docs-oasis-open-org:ws-dd:ns:discovery:2009:01"
        if discovery_namespace.endswith("/2009/01")
        else "urn:schemas-xmlsoap-org:ws:2005:04:discovery"
    )

    type_filter = (
        "<d:Types>dn:NetworkVideoTransmitter</d:Types>"
        if filtered
        else ""
    )

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="{SOAP}" xmlns:a="{addressing_namespace}"
 xmlns:d="{discovery_namespace}"
 xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
  <s:Header>
    <a:Action s:mustUnderstand="1">{discovery_namespace}/Probe</a:Action>
    <a:MessageID>{message_id}</a:MessageID>
    <a:ReplyTo>
      <a:Address>{addressing_namespace}/role/anonymous</a:Address>
    </a:ReplyTo>
    <a:To s:mustUnderstand="1">{destination}</a:To>
  </s:Header>
  <s:Body><d:Probe>{type_filter}</d:Probe></s:Body>
</s:Envelope>'''.encode("utf-8")


def _children_by_local_name(root, wanted):
    for node in root.iter():
        if _local(node.tag) == wanted:
            yield node


def _first_child_text(node, wanted):
    for child in node.iter():
        if _local(child.tag) == wanted:
            return _text(child)
    return ""


def _message_type(root):
    for node in root.iter():
        if _local(node.tag) == "Body":
            for child in node:
                return _local(child.tag)
            return "EmptyBody"
    return "Unknown"


def _parse_probe_matches(payload, source_address):
    root = ET.fromstring(payload)
    devices = []

    for match in _children_by_local_name(root, "ProbeMatch"):
        xaddrs = _first_child_text(match, "XAddrs")
        scopes = _first_child_text(match, "Scopes")
        endpoint = _first_child_text(match, "Address")
        scope_data = _scope_values(scopes)
        addresses = xaddrs.split() or [
            f"http://{source_address}/onvif/device_service"
        ]

        for xaddr in addresses:
            parsed = urlparse(xaddr)
            devices.append(
                {
                    "ip": parsed.hostname or source_address,
                    "xaddr": xaddr,
                    "endpoint": endpoint,
                    "name": scope_data.get("name", ""),
                    "hardware": scope_data.get("hardware", ""),
                    "location": scope_data.get("location", ""),
                    "profiles": scope_data.get("profile", ""),
                    "scopes": scopes,
                    "source_ip": source_address,
                }
            )

    return root, devices


def _open_probe_socket(interface):
    address = interface["address"]
    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM,
        socket.IPPROTO_UDP,
    )
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 0)
    sock.setsockopt(
        socket.IPPROTO_IP,
        socket.IP_MULTICAST_IF,
        socket.inet_aton(address),
    )
    sock.bind((address, 0))
    sock.setblocking(False)
    return sock


def _open_multicast_listener(interface):
    address = interface["address"]
    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM,
        socket.IPPROTO_UDP,
    )
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        sock.bind(("0.0.0.0", 3702))
    except OSError:
        sock.bind((address, 3702))

    membership = (
        socket.inet_aton("239.255.255.250")
        + socket.inet_aton(address)
    )
    sock.setsockopt(
        socket.IPPROTO_IP,
        socket.IP_ADD_MEMBERSHIP,
        membership,
    )
    sock.setblocking(False)
    return sock


def discover(timeout=5.0):
    import select
    import time

    interfaces = _ipv4_interfaces()
    diagnostics = {
        "interfaces": interfaces,
        "probes_sent": 0,
        "packets_received": 0,
        "xml_packets": 0,
        "probe_matches": 0,
        "parse_errors": 0,
        "message_types": {},
        "socket_errors": [],
        "unknown_xml_samples": [],
        "events": [],
    }

    if not interfaces:
        diagnostics["events"].append(
            "Aucune interface IPv4 active détectée."
        )
        return {"devices": [], "diagnostics": diagnostics}

    sockets = []

    for interface in interfaces:
        address = interface["address"]

        try:
            probe_socket = _open_probe_socket(interface)
            sockets.append(
                {
                    "socket": probe_socket,
                    "interface": interface,
                    "role": "probe",
                }
            )
            diagnostics["events"].append(
                f"Socket probe prête sur {interface['name']} "
                f"({address}:{probe_socket.getsockname()[1]})."
            )
        except OSError as exc:
            diagnostics["socket_errors"].append(
                f"Probe {interface['name']} ({address}) : {exc}"
            )

        try:
            listener = _open_multicast_listener(interface)
            sockets.append(
                {
                    "socket": listener,
                    "interface": interface,
                    "role": "listener3702",
                }
            )
            diagnostics["events"].append(
                f"Listener multicast actif sur {interface['name']} "
                f"({address}:3702)."
            )
        except OSError as exc:
            diagnostics["socket_errors"].append(
                f"Listener 3702 {interface['name']} ({address}) : {exc}"
            )

    probe_sockets = [
        entry for entry in sockets if entry["role"] == "probe"
    ]

    if not probe_sockets:
        return {"devices": [], "diagnostics": diagnostics}

    variants = (
        {
            "label": "legacy",
            "discovery":
                "http://schemas.xmlsoap.org/ws/2005/04/discovery",
            "addressing":
                "http://schemas.xmlsoap.org/ws/2004/08/addressing",
        },
        {
            "label": "modern",
            "discovery":
                "http://docs.oasis-open.org/ws-dd/ns/discovery/2009/01",
            "addressing":
                "http://www.w3.org/2005/08/addressing",
        },
    )

    target = ("239.255.255.250", 3702)

    try:
        for round_index in range(2):
            for socket_entry in probe_sockets:
                sock = socket_entry["socket"]
                interface = socket_entry["interface"]

                for variant in variants:
                    for filtered in (True, False):
                        probe = _probe_xml(
                            variant["discovery"],
                            variant["addressing"],
                            filtered,
                        )
                        try:
                            sock.sendto(probe, target)
                            diagnostics["probes_sent"] += 1
                            diagnostics["events"].append(
                                f"Probe {variant['label']} "
                                f"{'ONVIF' if filtered else 'générique'} "
                                f"envoyé via {interface['name']} "
                                f"({interface['address']})."
                            )
                        except OSError as exc:
                            diagnostics["socket_errors"].append(
                                f"Envoi via {interface['name']} : {exc}"
                            )

            if round_index == 0:
                time.sleep(0.35)

        deadline = time.monotonic() + max(
            1.0,
            min(float(timeout), 12.0),
        )
        found = {}

        while time.monotonic() < deadline:
            readable, _, _ = select.select(
                [entry["socket"] for entry in sockets],
                [],
                [],
                0.25,
            )

            for sock in readable:
                while True:
                    try:
                        payload, remote = sock.recvfrom(65535)
                    except BlockingIOError:
                        break
                    except OSError as exc:
                        diagnostics["socket_errors"].append(
                            f"Réception : {exc}"
                        )
                        break

                    source_ip = remote[0]
                    diagnostics["packets_received"] += 1

                    try:
                        root, devices = _parse_probe_matches(
                            payload,
                            source_ip,
                        )
                        diagnostics["xml_packets"] += 1
                        kind = _message_type(root)
                        diagnostics["message_types"][kind] = (
                            diagnostics["message_types"].get(kind, 0)
                            + 1
                        )
                    except ET.ParseError:
                        diagnostics["parse_errors"] += 1
                        continue

                    diagnostics["probe_matches"] += len(devices)

                    if (
                        not devices
                        and kind not in ("Probe", "Hello", "Bye")
                        and len(diagnostics["unknown_xml_samples"]) < 3
                    ):
                        lines = (
                            payload.decode("utf-8", errors="replace")
                            .replace("\r", "")
                            .splitlines()
                        )
                        diagnostics["unknown_xml_samples"].append(
                            {
                                "source_ip": source_ip,
                                "message_type": kind,
                                "lines": lines[:12],
                            }
                        )

                    local_addresses = {
                        item["address"]
                        for item in interfaces
                    }

                    for device in devices:
                        normalized_ip = _usable_discovery_ip(
                            str(device.get("ip", "")),
                            str(device.get("source_ip", "")),
                            local_addresses,
                        )

                        if not normalized_ip:
                            diagnostics["events"].append(
                                "Réponse ignorée : adresse locale, IPv6 ou APIPA "
                                f"({device.get('ip') or device.get('source_ip')})."
                            )
                            continue

                        device["ip"] = normalized_ip
                        key = normalized_ip

                        current = found.get(key)

                        if current is None:
                            current = dict(device)
                            current["xaddrs"] = []
                            found[key] = current

                        xaddr = device.get("xaddr", "")

                        if xaddr:
                            parsed_xaddr = urlparse(xaddr)
                            xaddr_host = parsed_xaddr.hostname or ""
                            keep_xaddr = True

                            if xaddr_host:
                                try:
                                    xaddr_ip = ipaddress.ip_address(xaddr_host)
                                    keep_xaddr = (
                                        xaddr_ip.version == 4
                                        and not xaddr_ip.is_link_local
                                        and xaddr_host not in local_addresses
                                        and xaddr_host == normalized_ip
                                    )
                                except ValueError:
                                    keep_xaddr = True

                            if (
                                keep_xaddr
                                and xaddr not in current["xaddrs"]
                            ):
                                current["xaddrs"].append(xaddr)

                        # Prefer the standard ONVIF device_service endpoint,
                        # then HTTPS, then the first discovered address.
                        candidates = current["xaddrs"]

                        standard = [
                            value
                            for value in candidates
                            if "/onvif/device_service" in value
                        ]

                        https = [
                            value
                            for value in candidates
                            if value.startswith("https://")
                        ]

                        standard_http = [
                            value
                            for value in standard
                            if value.startswith("http://")
                        ]

                        preferred = (
                            standard_http[0]
                            if standard_http
                            else standard[0]
                            if standard
                            else https[0]
                            if https
                            else candidates[0]
                            if candidates
                            else ""
                        )

                        current["xaddr"] = preferred

                        for field in (
                            "name",
                            "hardware",
                            "location",
                            "profiles",
                            "scopes",
                            "endpoint",
                        ):
                            if (
                                not current.get(field)
                                and device.get(field)
                            ):
                                current[field] = device[field]

                    diagnostics["events"].append(
                        f"Message {kind} reçu de {source_ip}"
                        + (
                            f" : {len(devices)} ProbeMatch."
                            if devices
                            else "."
                        )
                    )

        devices = sorted(
            found.values(),
            key=lambda item: (
                item.get("ip", ""),
                item.get("xaddr", ""),
            ),
        )

        diagnostics["events"].append(
            f"Recherche terminée : {len(devices)} équipement(s) unique(s)."
        )

        return {
            "devices": devices,
            "diagnostics": diagnostics,
        }

    finally:
        for entry in sockets:
            try:
                entry["socket"].close()
            except OSError:
                pass


DEBUG_LOG = Path("/tmp/pidecoder-onvif.log")


def _debug_reset():
    try:
        DEBUG_LOG.write_text(
            "PiDecoder ONVIF Debug v0.9.2\n"
            "================================\n",
            encoding="utf-8",
        )
        os.chmod(DEBUG_LOG, 0o600)
    except OSError:
        pass


def _debug_write(title, content=""):
    try:
        timestamp = datetime.now().isoformat(timespec="seconds")

        with DEBUG_LOG.open("a", encoding="utf-8") as handle:
            handle.write(f"\n[{timestamp}] {title}\n")
            handle.write("-" * 72 + "\n")

            if content:
                handle.write(str(content))

                if not str(content).endswith("\n"):
                    handle.write("\n")

    except OSError:
        pass


def _pretty_xml(payload):
    if isinstance(payload, bytes):
        raw = payload.decode("utf-8", errors="replace")
    else:
        raw = str(payload)

    try:
        root = ET.fromstring(raw)
        ET.indent(root, space="  ")
        return ET.tostring(root, encoding="unicode")
    except ET.ParseError:
        return raw


def _usable_discovery_ip(candidate, source_address, local_addresses):
    def valid(value):
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            return False

        return (
            address.version == 4
            and not address.is_link_local
            and not address.is_loopback
            and value not in local_addresses
        )

    if valid(candidate):
        return candidate

    if valid(source_address):
        return source_address

    return ""


def _wsse_header(c):
    if not c.username:
        return ""

    nonce = os.urandom(16)

    created = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

    digest = hashlib.sha1(
        nonce
        + created.encode("utf-8")
        + c.password.encode("utf-8")
    ).digest()

    token_id = "UsernameToken-" + uuid.uuid4().hex

    password_digest_uri = (
        "http://docs.oasis-open.org/wss/2004/01/"
        "oasis-200401-wss-username-token-profile-1.0"
        "#PasswordDigest"
    )

    base64_binary_uri = (
        "http://docs.oasis-open.org/wss/2004/01/"
        "oasis-200401-wss-soap-message-security-1.0"
        "#Base64Binary"
    )

    return f"""
<wsse:Security
 s:mustUnderstand="1"
 xmlns:wsse="{WSSE}"
 xmlns:wsu="{WSU}">
  <wsse:UsernameToken wsu:Id="{token_id}">
    <wsse:Username>{c.username}</wsse:Username>
    <wsse:Password Type="{password_digest_uri}">{base64.b64encode(digest).decode("ascii")}</wsse:Password>
    <wsse:Nonce EncodingType="{base64_binary_uri}">{base64.b64encode(nonce).decode("ascii")}</wsse:Nonce>
    <wsu:Created>{created}</wsu:Created>
  </wsse:UsernameToken>
</wsse:Security>
"""

def _soap(
    endpoint,
    action,
    body,
    c,
    timeout=8,
    operation="SOAP",
):
    envelope = f'''<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope
 xmlns:s="{SOAP}"
 xmlns:tds="{TDS}"
 xmlns:trt="{TRT}"
 xmlns:tt="{TT}"
 xmlns:tptz="{TPTZ}"
 xmlns:wsse="{WSSE}"
 xmlns:wsu="{WSU}">
  <s:Header>{_wsse_header(c)}</s:Header>
  <s:Body>{body}</s:Body>
</s:Envelope>'''.encode("utf-8")

    _debug_write(
        f"{operation} — REQUÊTE",
        (
            f"POST {endpoint}\n"
            f"Action: {action}\n"
            f"Utilisateur: {c.username or '(vide)'}\n\n"
            f"{_pretty_xml(envelope)}"
        ),
    )

    password_manager = HTTPPasswordMgrWithDefaultRealm()
    password_manager.add_password(
        None,
        endpoint,
        c.username,
        c.password,
    )

    opener = build_opener(
        HTTPDigestAuthHandler(password_manager)
    )

    request = Request(
        endpoint,
        data=envelope,
        method="POST",
        headers={
            "Content-Type": (
                "application/soap+xml; "
                f'charset=utf-8; action="{action}"'
            ),
            "SOAPAction": f'"{action}"',
            "User-Agent": "PiDecoder/0.9.2",
        },
    )

    try:
        with opener.open(request, timeout=timeout) as response:
            payload = response.read()

            _debug_write(
                f"{operation} — RÉPONSE HTTP {response.status}",
                (
                    f"URL finale: {response.geturl()}\n"
                    f"Content-Type: {response.headers.get('Content-Type', '')}\n\n"
                    f"{_pretty_xml(payload)}"
                ),
            )

    except HTTPError as exc:
        try:
            error_payload = exc.read()
        except Exception:
            error_payload = b""

        _debug_write(
            f"{operation} — HTTP ERROR {exc.code}",
            (
                f"URL: {endpoint}\n"
                f"Raison: {exc.reason}\n"
                f"Headers:\n{exc.headers}\n"
                f"Corps:\n{_pretty_xml(error_payload)}"
            ),
        )

        raise OnvifError(
            f"{operation} : HTTP {exc.code} {exc.reason}. Voir {DEBUG_LOG}"
        ) from exc

    except URLError as exc:
        _debug_write(
            f"{operation} — ERREUR URL",
            f"URL: {endpoint}\nErreur: {exc}",
        )

        raise OnvifError(
            f"{operation} : connexion impossible. Voir {DEBUG_LOG}"
        ) from exc

    except Exception as exc:
        _debug_write(
            f"{operation} — ERREUR",
            f"URL: {endpoint}\nErreur: {type(exc).__name__}: {exc}",
        )

        raise OnvifError(
            f"{operation} : {exc}. Voir {DEBUG_LOG}"
        ) from exc

    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        _debug_write(
            f"{operation} — XML INVALIDE",
            _pretty_xml(payload),
        )

        raise OnvifError(
            f"{operation} : réponse XML invalide. Voir {DEBUG_LOG}"
        ) from exc

    fault = root.find(".//s:Fault", NS)

    if fault is not None:
        reason = _text(
            fault.find(".//s:Text", NS),
            "Erreur ONVIF",
        )

        _debug_write(
            f"{operation} — SOAP FAULT",
            reason,
        )

        raise OnvifError(
            f"{operation} : {reason}. Voir {DEBUG_LOG}"
        )

    return root

def get_device_information(x,c):
    root=_soap(
        x,
        f'{TDS}/GetDeviceInformation',
        '<tds:GetDeviceInformation/>',
        c,
        operation='GetDeviceInformation',
    ); response=root.find('.//tds:GetDeviceInformationResponse',NS)
    if response is None: raise OnvifError('GetDeviceInformation non supporté')
    return {_local(child.tag):_text(child) for child in response}

def get_capabilities(x, c):
    root = _soap(
        x,
        f'{TDS}/GetCapabilities',
        (
            '<tds:GetCapabilities>'
            '<tds:Category>All</tds:Category>'
            '</tds:GetCapabilities>'
        ),
        c,
        operation='GetCapabilities',
    )

    result = {}

    capabilities_node = None

    for node in root.iter():
        if _local(node.tag) == "Capabilities":
            capabilities_node = node
            break

    if capabilities_node is None:
        _debug_write(
            "GetCapabilities — PARSING",
            "Aucun nœud Capabilities trouvé.",
        )
        return result

    wanted = {
        "Media": "media",
        "PTZ": "ptz",
        "Events": "events",
        "Imaging": "imaging",
        "Device": "device",
        "Analytics": "analytics",
    }

    for child in capabilities_node:
        local_name = _local(child.tag)
        key = wanted.get(local_name)

        if not key:
            continue

        xaddr = ""

        for descendant in child.iter():
            if _local(descendant.tag) == "XAddr":
                xaddr = _text(descendant)
                break

        if xaddr:
            result[key] = xaddr

    _debug_write(
        "GetCapabilities — PARSING",
        "\n".join(
            f"{name}: {value}"
            for name, value in sorted(result.items())
        ) or "Aucune capacité exploitable.",
    )

    return result

def get_profiles(x, c):
    root = _soap(
        x,
        f'{TRT}/GetProfiles',
        '<trt:GetProfiles/>',
        c,
        operation='GetProfiles',
    )

    profiles = []

    for node in root.iter():
        if _local(node.tag) != "Profiles":
            continue

        token = node.attrib.get("token", "")
        name = ""
        width = None
        height = None
        fps = None
        encoding = ""
        ptz = False
        ptz_configuration_token = ""

        for descendant in node.iter():
            local_name = _local(descendant.tag)

            if local_name == "Name" and not name:
                name = _text(descendant)

            elif local_name == "Width" and width is None:
                value = _text(descendant)

                try:
                    width = int(value)
                except ValueError:
                    width = None

            elif local_name == "Height" and height is None:
                value = _text(descendant)

                try:
                    height = int(value)
                except ValueError:
                    height = None

            elif local_name == "Encoding" and not encoding:
                encoding = _text(descendant)

            elif local_name == "FrameRateLimit" and fps is None:
                value = _text(descendant)

                try:
                    fps = float(value)
                except ValueError:
                    fps = None

            elif local_name == "PTZConfiguration":
                ptz = True
                ptz_configuration_token = (
                    descendant.attrib.get(
                        "token",
                        "",
                    )
                )

        profiles.append(
            {
                "token": token,
                "name": name or token,
                "width": width,
                "height": height,
                "fps": fps,
                "encoding": encoding,
                "ptz": ptz,
                "ptz_configuration_token":
                    ptz_configuration_token,
            }
        )

    _debug_write(
        "GetProfiles — PARSING",
        "\n".join(
            (
                f"{index + 1}. "
                f"{profile['name']} | "
                f"token={profile['token']} | "
                f"resolution={profile['width']}x{profile['height']} | "
                f"fps={profile['fps']} | "
                f"encoding={profile['encoding']} | "
                f"ptz={profile['ptz']}"
            )
            for index, profile in enumerate(profiles)
        ) or "Aucun profil retourné.",
    )

    return profiles

def get_stream_uri(x, token, c):
    root = _soap(
        x,
        f'{TRT}/GetStreamUri',
        (
            '<trt:GetStreamUri>'
            '<trt:StreamSetup>'
            '<tt:Stream>RTP-Unicast</tt:Stream>'
            '<tt:Transport><tt:Protocol>RTSP</tt:Protocol></tt:Transport>'
            '</trt:StreamSetup>'
            f'<trt:ProfileToken>{token}</trt:ProfileToken>'
            '</trt:GetStreamUri>'
        ),
        c,
        operation=f'GetStreamUri [{token}]',
    )

    uri = ""

    for node in root.iter():
        if _local(node.tag) == "Uri":
            candidate = _text(node)

            if candidate.lower().startswith("rtsp://"):
                uri = candidate
                break

    if not uri:
        raise OnvifError(
            f'Aucune URI RTSP retournée pour le profil {token}'
        )

    _debug_write(
        f'GetStreamUri [{token}] — PARSING',
        uri,
    )

    return uri

def get_presets(x,token,c):
    root=_soap(x,f'{TPTZ}/GetPresets',f'<tptz:GetPresets><tptz:ProfileToken>{token}</tptz:ProfileToken></tptz:GetPresets>',c); result=[]
    for node in root.findall('.//tptz:Preset',NS): result.append({'token':node.attrib.get('token',''),'name':_text(node.find('tt:Name',NS),node.attrib.get('token',''))})
    return result

def identify_device(x, username, password):
    _debug_reset()
    _debug_write(
        "DÉBUT IDENTIFICATION",
        f"Device XAddr: {x}\nUtilisateur: {username or '(vide)'}",
    )

    """
    v0.9.1 identification milestone.

    Reads only:
    - GetDeviceInformation
    - GetCapabilities
    - GetProfiles

    It reads RTSP URIs and PTZ presets but never moves the camera.
    """
    credentials = Credentials(
        username,
        password,
    )

    information = get_device_information(
        x,
        credentials,
    )

    capabilities = get_capabilities(
        x,
        credentials,
    )

    media_xaddr = capabilities.get(
        "media",
        "",
    )

    ptz_xaddr = capabilities.get(
        "ptz",
        "",
    )

    _debug_write(
        "SERVICES IDENTIFIÉS",
        (
            f"Media XAddr: {media_xaddr or '(absent)'}\n"
            f"PTZ XAddr: {ptz_xaddr or '(absent)'}"
        ),
    )

    profiles = (
        get_profiles(
            media_xaddr,
            credentials,
        )
        if media_xaddr
        else []
    )

    for profile in profiles:
        try:
            profile["stream_uri"] = get_stream_uri(
                media_xaddr,
                profile.get("token", ""),
                credentials,
            )
            profile["stream_error"] = ""
        except OnvifError as exc:
            profile["stream_uri"] = ""
            profile["stream_error"] = str(exc)

    presets = {}

    if ptz_xaddr:
        for profile in profiles:
            if not profile.get("ptz"):
                continue

            token = str(profile.get("token", "")).strip()

            if not token:
                continue

            try:
                presets[token] = get_presets(
                    ptz_xaddr,
                    token,
                    credentials,
                )
                profile["preset_error"] = ""
            except OnvifError as exc:
                presets[token] = []
                profile["preset_error"] = str(exc)

    _debug_write(
        "IDENTIFICATION TERMINÉE",
        (
            f"Fabricant: {information.get('Manufacturer', '')}\n"
            f"Modèle: {information.get('Model', '')}\n"
            f"Profils: {len(profiles)}"
        ),
    )

    return {
        "debug_log": str(DEBUG_LOG),
        "device_xaddr": x,
        "information": information,
        "capabilities": capabilities,
        "profiles": profiles,
        "profile_count": len(profiles),
        "media_xaddr": media_xaddr,
        "ptz_xaddr": ptz_xaddr,
        "ptz_advertised": bool(
            ptz_xaddr
        ),
        "ptz_supported": bool(
            ptz_xaddr
            and any(
                profile.get("ptz")
                for profile in profiles
            )
        ),
        "presets": presets,
    }


def inspect_device(x,username,password):
    c=Credentials(username,password); info=get_device_information(x,c); caps=get_capabilities(x,c); media=caps.get('media',''); profiles=get_profiles(media,c) if media else []
    for p in profiles:
        try:p['stream_uri']=get_stream_uri(media,p['token'],c)
        except OnvifError as exc:p['stream_error']=str(exc)
    presets={};ptz=caps.get('ptz','')
    if ptz:
        for p in profiles:
            if p['ptz']:
                try:presets[p['token']]=get_presets(ptz,p['token'],c)
                except OnvifError:presets[p['token']]=[]
    return {'device_xaddr':x,'information':info,'capabilities':caps,'profiles':profiles,'presets':presets,'ptz_supported':bool(ptz and any(p['ptz'] for p in profiles))}

def continuous_move(x,token,c,pan=0,tilt=0,zoom=0):
    _soap(x,f'{TPTZ}/ContinuousMove',f'<tptz:ContinuousMove><tptz:ProfileToken>{token}</tptz:ProfileToken><tptz:Velocity><tt:PanTilt x="{pan:.3f}" y="{tilt:.3f}"/><tt:Zoom x="{zoom:.3f}"/></tptz:Velocity><tptz:Timeout>PT10S</tptz:Timeout></tptz:ContinuousMove>',c)
def stop(x,token,c):
    _soap(x,f'{TPTZ}/Stop',f'<tptz:Stop><tptz:ProfileToken>{token}</tptz:ProfileToken><tptz:PanTilt>true</tptz:PanTilt><tptz:Zoom>true</tptz:Zoom></tptz:Stop>',c)
def goto_preset(x,token,preset,c):
    _soap(x,f'{TPTZ}/GotoPreset',f'<tptz:GotoPreset><tptz:ProfileToken>{token}</tptz:ProfileToken><tptz:PresetToken>{preset}</tptz:PresetToken></tptz:GotoPreset>',c)
