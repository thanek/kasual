"""SSDP M-SEARCH discovery for UPnP MediaServer:1 (DLNA) devices."""

import socket
import time
import xml.etree.ElementTree as ET
from urllib.parse import urljoin
from urllib.request import urlopen

_SSDP_ADDR = "239.255.255.250"
_SSDP_PORT = 1900
_MX = 3

_M_SEARCH = (
    "M-SEARCH * HTTP/1.1\r\n"
    f"HOST: {_SSDP_ADDR}:{_SSDP_PORT}\r\n"
    'MAN: "ssdp:discover"\r\n'
    f"MX: {_MX}\r\n"
    "ST: urn:schemas-upnp-org:device:MediaServer:1\r\n"
    "\r\n"
)


def _device_info(location: str) -> dict:
    """Fetch device descriptor and return {'name': str, 'icon_url': str}."""
    try:
        with urlopen(location, timeout=3) as resp:
            data = resp.read()
        root = ET.fromstring(data)
        ns = {"d": "urn:schemas-upnp-org:device-1-0"}
        name_el = root.find(".//d:friendlyName", ns)
        name = name_el.text if name_el is not None else None

        icon_url = _best_icon_url(root, ns, location)
        return {"name": name or location, "icon_url": icon_url}
    except Exception:
        return {"name": location, "icon_url": ""}


def _best_icon_url(root: ET.Element, ns: dict, base: str) -> str:
    """Pick the best icon from <iconList>: prefer PNG, largest up to 256px."""
    best_url = ""
    best_score = -1
    for icon in root.findall(".//d:icon", ns):
        mime = (icon.findtext("d:mimetype", namespaces=ns) or "").lower()
        if mime not in ("image/png", "image/jpeg", "image/jpg"):
            continue
        try:
            w = int(icon.findtext("d:width", namespaces=ns) or 0)
            h = int(icon.findtext("d:height", namespaces=ns) or 0)
        except ValueError:
            w = h = 0
        size = max(w, h)
        if size > 256:
            size = 256 - (size - 256)  # penalise oversized icons
        png_bonus = 10 if "png" in mime else 0
        score = size + png_bonus
        if score > best_score:
            url = (icon.findtext("d:url", namespaces=ns) or "").strip()
            if url:
                best_score = score
                best_url = urljoin(base, url)
    return best_url


def discover(timeout: float = 5.0) -> list[dict]:
    """Return list of {'name': str, 'location': str, 'icon_url': str} for each found DLNA server."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.settimeout(0.5)

    try:
        sock.sendto(_M_SEARCH.encode(), (_SSDP_ADDR, _SSDP_PORT))
        seen: set[str] = set()
        servers: list[dict] = []
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            try:
                data, _ = sock.recvfrom(4096)
            except socket.timeout:
                continue

            headers: dict[str, str] = {}
            for line in data.decode(errors="replace").split("\r\n")[1:]:
                if ":" in line:
                    k, _, v = line.partition(":")
                    headers[k.strip().upper()] = v.strip()

            location = headers.get("LOCATION", "")
            usn = headers.get("USN", location)
            if not location or usn in seen:
                continue
            seen.add(usn)

            info = _device_info(location)
            servers.append({"name": info["name"], "location": location,
                            "icon_url": info["icon_url"]})

        return servers
    finally:
        sock.close()
