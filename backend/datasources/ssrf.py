import ipaddress
import socket
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)


class SSRFBlocked(Exception):
    pass


PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_private(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in net for net in PRIVATE_NETWORKS)
    except ValueError:
        return True  # unparseable = block


def _resolve_host(hostname: str, timeout: float = 5.0) -> list:
    old = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        infos = socket.getaddrinfo(hostname, None)
        return list({info[4][0] for info in infos})
    except Exception as e:
        raise SSRFBlocked(f"DNS resolution failed for {hostname}: {e}")
    finally:
        socket.setdefaulttimeout(old)


def assert_public_mongo_uri(uri: str) -> None:
    """
    Raises SSRFBlocked if the resolved host is a private/loopback/link-local IP.
    Handles mongodb:// and mongodb+srv://.
    """
    if not uri or not isinstance(uri, str):
        raise SSRFBlocked("Empty URI")

    parsed = urlparse(uri if "://" in uri else "mongodb://" + uri)
    host = parsed.hostname
    if not host:
        raise SSRFBlocked("No hostname in URI")

    # Block obvious local names
    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        raise SSRFBlocked(f"Blocked host: {host}")

    scheme = parsed.scheme or "mongodb"
    hosts_to_check = [host]

    if scheme == "mongodb+srv" or uri.startswith("mongodb+srv://"):
        # Resolve SRV
        try:
            import dns.resolver
            answers = dns.resolver.resolve(f"_mongodb._tcp.{host}", "SRV")
            for rdata in answers:
                hosts_to_check.append(str(rdata.target).rstrip("."))
        except Exception as e:
            logger.warning(f"SRV lookup failed for {host}: {e}")
            # still check the main host

    for h in hosts_to_check:
        try:
            ips = _resolve_host(h)
        except SSRFBlocked:
            raise
        except Exception as e:
            raise SSRFBlocked(f"Cannot resolve {h}: {e}")
        for ip in ips:
            if _is_private(ip):
                raise SSRFBlocked(f"Private IP {ip} resolved for host {h}")
