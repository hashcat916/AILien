"""Network and server diagnostic tools."""
import itertools
import re
import socket
import subprocess
from datetime import datetime

from tools import tool


def _run_cmd(cmd: list[str], timeout: int = 15) -> tuple[int, str]:
    """Run a shell command and return (returncode, stdout+stderr)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        output = r.stdout.strip() or r.stderr.strip()
        return r.returncode, output
    except subprocess.TimeoutExpired:
        return -1, "Command timed out."
    except FileNotFoundError:
        return -2, f"Command not found: {cmd[0]}"
    except Exception as e:
        return -3, str(e)


@tool(
    name="ping_host",
    description="Ping a host to check if it's reachable on the network.",
    params={
        "host": {"type": "string", "description": "Hostname or IP address to ping (e.g. google.com, 8.8.8.8)"},
        "count": {"type": "integer", "description": "Number of pings to send (default: 4)", "default": 4},
    },
    required=["host"],
)
def ping_host(host: str, count: int = 4) -> str:
    """Ping a host to check network connectivity."""
    # Clean the host — remove protocol prefixes
    host = re.sub(r"^https?://", "", host).split("/")[0]

    code, output = _run_cmd(["ping", "-c", str(count), "-W", "3", host], timeout=count * 4 + 5)
    if code == 0:
        # Extract summary line for clean output
        lines = output.split("\n")
        summary = [l for l in lines if "packets transmitted" in l or "min/avg/max" in l or "rtt" in l]
        if summary:
            detail = "\n".join(summary[-3:])
            return f"{host} is reachable.\n{detail}"
        return f"{host} is reachable.\n{output[:300]}"
    elif code == -1:
        return f"Ping to {host} timed out."
    elif code == -2:
        return f"ping command not found. Try 'check_port' or 'http_check' instead."
    else:
        return f"{host} is not responding.\n{output[:300]}"


@tool(
    name="dns_lookup",
    description="Look up DNS records for a domain (A, AAAA, MX, NS, TXT records).",
    params={
        "domain": {"type": "string", "description": "Domain name to look up (e.g. google.com)"},
        "record_type": {
            "type": "string",
            "description": "DNS record type: A (IPv4), AAAA (IPv6), MX (mail), NS (nameservers), TXT (text), ALL (all available)",
            "default": "ALL",
            "enum": ["A", "AAAA", "MX", "NS", "TXT", "ALL"],
        },
    },
    required=["domain"],
)
def dns_lookup(domain: str, record_type: str = "ALL") -> str:
    """Look up DNS records for a domain."""
    # Clean the domain
    domain = re.sub(r"^https?://", "", domain).split("/")[0]
    # Strip trailing dots
    domain = domain.rstrip(".")

    try:
        import dns.resolver
        resolver = dns.resolver.Resolver()
        resolver.timeout = 5
        resolver.lifetime = 5
    except ImportError:
        # Fall back to dig command
        return _dns_lookup_fallback(domain, record_type)

    record_types = {
        "A": "A",
        "AAAA": "AAAA",
        "MX": "MX",
        "NS": "NS",
        "TXT": "TXT",
    }

    # Normalize ALL
    if record_type == "ALL":
        types_to_query = list(record_types.keys())
    elif record_type in record_types:
        types_to_query = [record_type]
    else:
        return f"Unknown record type: {record_type}"

    results = []
    for rt in types_to_query:
        try:
            answers = resolver.resolve(domain, rt)
            rdata = [str(a) for a in answers]
            results.append(f"  {rt:4}  {', '.join(rdata)}")
        except dns.resolver.NoAnswer:
            results.append(f"  {rt:4}  (no records)")
        except dns.resolver.NXDOMAIN:
            return f"Domain does not exist: {domain}"
        except dns.exception.Timeout:
            results.append(f"  {rt:4}  (query timed out)")
        except Exception as e:
            results.append(f"  {rt:4}  ({e})")

    lines = [f"DNS records for {domain}:", "\n".join(results)]
    return "\n".join(lines)


def _dns_lookup_fallback(domain: str, record_type: str) -> str:
    """Fallback DNS lookup using the dig command."""
    types_map = {"A": "A", "AAAA": "AAAA", "MX": "MX", "NS": "NS", "TXT": "TXT", "ALL": "ANY"}
    rt = types_map.get(record_type, "ANY")

    code, output = _run_cmd(["dig", "+short", domain, rt], timeout=10)
    if code == 0 and output.strip():
        lines = output.strip().split("\n")
        return f"DNS {record_type} records for {domain}:\n  " + "\n  ".join(lines[:15])
    elif code == -2:
        # No dig either — use socket.gethostbyname as last resort
        try:
            ip = socket.gethostbyname(domain)
            return f"DNS A record for {domain}: {ip}\n(install dnsutils for full record types)"
        except socket.gaierror:
            return f"Could not resolve: {domain}"
    else:
        return f"Could not resolve {domain}. (dig not available, try installing dnsutils)"


@tool(
    name="check_port",
    description="Check if a network port is open on a host.",
    params={
        "host": {"type": "string", "description": "Hostname or IP address"},
        "port": {"type": "integer", "description": "Port number to check (e.g. 80, 443, 22)"},
        "protocol": {
            "type": "string",
            "description": "Protocol: 'tcp' or 'udp' (default: tcp)",
            "default": "tcp",
            "enum": ["tcp", "udp"],
        },
    },
    required=["host", "port"],
)
def check_port(host: str, port: int, protocol: str = "tcp") -> str:
    """Check if a port is open on a remote host."""
    host = re.sub(r"^https?://", "", host).split("/")[0]

    if protocol == "udp":
        # UDP check — best-effort
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(3)
            s.sendto(b"", (host, port))
            try:
                s.recvfrom(1024)
                return f"Port {port}/UDP on {host} appears open (received response)."
            except socket.timeout:
                return f"Port {port}/UDP on {host}: no response (open or filtered)."
            finally:
                s.close()
        except Exception as e:
            return f"Could not check port {port}/UDP on {host}: {e}"

    # TCP check
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(4)
        result = s.connect_ex((host, port))
        s.close()

        # Common services
        services = {20: "FTP data", 21: "FTP control", 22: "SSH", 23: "Telnet",
                    25: "SMTP", 53: "DNS", 80: "HTTP", 110: "POP3",
                    143: "IMAP", 443: "HTTPS", 465: "SMTPS", 587: "SMTP submission",
                    993: "IMAPS", 995: "POP3S", 3306: "MySQL", 5432: "PostgreSQL",
                    6379: "Redis", 8080: "HTTP-alt", 8443: "HTTPS-alt",
                    27017: "MongoDB"}

        service = services.get(port, "")
        svc_tag = f" ({service})" if service else ""

        if result == 0:
            return f"Port {port}/TCP on {host} is OPEN{svc_tag}."
        else:
            return f"Port {port}/TCP on {host} is CLOSED or filtered{svc_tag}."

    except socket.gaierror:
        return f"Could not resolve hostname: {host}"
    except Exception as e:
        return f"Error checking port: {e}"


@tool(
    name="trace_route",
    description="Trace the network path to a host (shows hops between your computer and the target).",
    params={
        "host": {"type": "string", "description": "Hostname or IP address to trace (e.g. google.com)"},
        "max_hops": {"type": "integer", "description": "Maximum number of hops (default: 20)", "default": 20},
    },
    required=["host"],
)
def trace_route(host: str, max_hops: int = 20) -> str:
    """Trace the network route to a host."""
    host = re.sub(r"^https?://", "", host).split("/")[0]

    # Try traceroute first, then tracepath
    cmd = ["traceroute", "-n", "-m", str(max_hops), "-w", "2", host]
    code, output = _run_cmd(cmd, timeout=60)

    if code == -2:
        # Try tracepath as fallback
        cmd = ["tracepath", "-n", "-m", str(max_hops), host]
        code, output = _run_cmd(cmd, timeout=60)

    if code == 0 and output.strip():
        lines = output.strip().split("\n")
        # Clean up the output — show first 25 lines max
        if len(lines) > 25:
            lines = lines[:25] + ["... (truncated)"]
        header = f"Traceroute to {host} ({max_hops} max hops):\n"
        return header + "\n".join(lines)

    elif code == -2:
        return "Neither traceroute nor tracepath are installed. Install with: sudo apt-get install traceroute"
    else:
        return f"Could not trace route to {host}.\n{output[:300]}"


@tool(
    name="http_check",
    description="Check if an HTTP/HTTPS server is responding and get its status code and headers.",
    params={
        "url": {"type": "string", "description": "Full URL to check (e.g. https://example.com)"},
        "timeout": {"type": "integer", "description": "Timeout in seconds (default: 10)", "default": 10},
        "follow_redirects": {
            "type": "boolean",
            "description": "Follow redirects (default: true)",
            "default": True,
        },
    },
    required=["url"],
)
def http_check(url: str, timeout: int = 10, follow_redirects: bool = True) -> str:
    """Check if an HTTP server is responding."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        import urllib.request as req
        import ssl

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        r = req.Request(url, method="HEAD")

        try:
            resp = req.urlopen(r, timeout=timeout, context=ctx)
            code = resp.status
            headers = dict(resp.headers)
            final_url = resp.url
            resp.close()
        except req.HTTPError as e:
            code = e.code
            headers = dict(e.headers)
            final_url = e.url if hasattr(e, "url") else url
        except req.URLError as e:
            return f"Could not reach {url}: {e.reason}"        # URLError with ConnectionRefusedError, timeout, etc.
        except req.URLError as e:
            return f"Could not reach {url}: {e.reason}"

        status_text = {
            200: "OK", 201: "Created", 204: "No Content",
            301: "Moved Permanently", 302: "Found", 303: "See Other", 307: "Temporary Redirect", 308: "Permanent Redirect",
            400: "Bad Request", 401: "Unauthorized", 403: "Forbidden", 404: "Not Found", 405: "Method Not Allowed",
            429: "Too Many Requests",
            500: "Internal Server Error", 502: "Bad Gateway", 503: "Service Unavailable", 504: "Gateway Timeout",
        }
        status_label = status_text.get(code, "Unknown")

        lines = [
            f"URL:    {final_url}",
            f"Status: {code} {status_label}",
        ]

        if final_url != url:
            lines.append(f"Redirect from: {url}")

        # Show key headers
        key_headers = ["server", "content-type", "content-length", "date", "location", "set-cookie"]
        shown = False
        for h in key_headers:
            if h in headers:
                if not shown:
                    lines.append(f"\nHeaders:")
                    shown = True
                lines.append(f"  {h}: {headers[h][:100]}")

        return "\n".join(lines)

    except ImportError:
        # Fallback to curl
        cmd = ["curl", "-s", "-I", "-m", str(timeout), url]
        if not follow_redirects:
            cmd.insert(2, "-L")
        code, output = _run_cmd(cmd, timeout=timeout + 5)
        if code == 0:
            return f"HTTP response for {url}:\n{output[:500]}"
        else:
            return f"Could not check {url}: {output[:200]}"
