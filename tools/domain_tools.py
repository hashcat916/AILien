"""Domain name research and WHOIS tools."""
import re
import subprocess
from datetime import datetime

from tools import tool


def _run_whois(domain: str, timeout: int = 15) -> tuple[int, str]:
    """Run whois on a domain and return (returncode, output)."""
    try:
        r = subprocess.run(
            ["whois", domain],
            capture_output=True, text=True, timeout=timeout,
        )
        return r.returncode, (r.stdout or r.stderr or "")
    except FileNotFoundError:
        return -2, "whois command not found. Install with: sudo apt-get install whois"
    except subprocess.TimeoutExpired:
        return -1, "WHOIS query timed out."
    except Exception as e:
        return -3, str(e)


def _is_domain_available(whois_text: str) -> bool | None:
    """Heuristic check if domain is available based on WHOIS output."""
    lower = whois_text.lower()

    # Common "not found" patterns across registries
    available_patterns = [
        "no match for",
        "no entries found",
        "not found",
        "no data found",
        "domain not found",
        "status: free",
        "no object found",
        "nothing found",
        "is available",
        "the queried object does not exist",
        "domain not registered",
        "no information available",
        "not registered",
        "domain available",
    ]
    for pat in available_patterns:
        if pat in lower:
            return True

    # If we see registry data, it's likely registered
    registered_patterns = [
        "domain name:",
        "registrar:",
        "creation date:",
        "registry expiry date:",
        "registrant name:",
        "name server:",
    ]
    for pat in registered_patterns:
        if pat in lower:
            return False

    # Uncertain
    return None


def _extract_whois_fields(text: str) -> dict[str, str]:
    """Extract useful fields from raw WHOIS text."""
    fields = {}

    # Common fields across registries — case-insensitive, take first match
    patterns = [
        ("registrar", r"(?im)^registrar:\s*(.+)"),
        ("creation_date", r"(?im)^(?:creation date|created|created on|creation date:|created date):\s*(.+)"),
        ("expiry_date", r"(?im)^(?:registry expiry date|expiry date|expiration date|expires|paid till|expire):\s*(.+)"),
        ("updated_date", r"(?im)^(?:updated date|last update|last updated|updated):\s*(.+)"),
        ("name_servers", r"(?im)^name server:\s*(.+)"),
        ("registrant_name", r"(?im)^registrant name:\s*(.+)"),
        ("registrant_org", r"(?im)^registrant organization:\s*(.+)"),
        ("status", r"(?im)^(?:domain status|status):\s*(.+)"),
    ]

    for key, pat in patterns:
        matches = re.findall(pat, text)
        if matches:
            val = matches[0].strip()
            if key == "name_servers":
                vals = [m.strip() for m in matches]
                fields[key] = ", ".join(vals[:5])
            else:
                fields[key] = val

    return fields


@tool(
    name="check_domain",
    description="Check if a domain name is available for registration via WHOIS lookup.",
    params={
        "domain": {"type": "string", "description": "Domain name to check (e.g. example.com)"},
    },
    required=["domain"],
)
def check_domain(domain: str) -> str:
    """Check if a domain is available for registration."""
    domain = re.sub(r"^www\.", "", domain.lower().strip())

    # Basic validation
    if not re.match(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.[a-z]{2,}$", domain):
        return f"Invalid domain format: {domain}. Use something like 'example.com'"

    code, output = _run_whois(domain)
    if code == -2:
        return output  # "whois not found"
    if code == -1:
        return f"WHOIS query for {domain} timed out."
    if code != 0 and code != 1:
        # whois may return 1 for "not found" which is fine, or errors
        if "no match for" in output.lower():
            pass  # This is OK — domain is available
        else:
            return f"WHOIS error for {domain}.\n{output[:200]}"

    available = _is_domain_available(output)

    if available is True:
        return f"✅ {domain} is AVAILABLE for registration!"
    elif available is False:
        fields = _extract_whois_fields(output)
        lines = [f"❌ {domain} is REGISTERED."]
        if fields.get("registrar"):
            lines.append(f"  Registrar: {fields['registrar']}")
        if fields.get("creation_date"):
            lines.append(f"  Created:   {fields['creation_date']}")
        if fields.get("expiry_date"):
            lines.append(f"  Expires:   {fields['expiry_date']}")
        if fields.get("name_servers"):
            lines.append(f"  NS:        {fields['name_servers']}")
        return "\n".join(lines)
    else:
        return f"⚠️  Could not determine availability for {domain}. The WHOIS data was ambiguous.\nRaw output (first 500 chars):\n{output[:500]}"


@tool(
    name="domain_whois",
    description="Get detailed WHOIS registration information for a domain.",
    params={
        "domain": {"type": "string", "description": "Domain name (e.g. example.com)"},
    },
    required=["domain"],
)
def domain_whois(domain: str) -> str:
    """Get detailed WHOIS information for a domain."""
    domain = re.sub(r"^www\.", "", domain.lower().strip())

    if not re.match(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.[a-z]{2,}$", domain):
        return f"Invalid domain format: {domain}"

    code, output = _run_whois(domain)
    if code == -2:
        return output

    available = _is_domain_available(output)
    if available is True:
        return f"ℹ️  {domain} is AVAILABLE. No registration data to display."

    fields = _extract_whois_fields(output)
    lines = [f"WHOIS Information for: {domain}", "=" * 40]

    if not fields:
        # Show raw summary
        raw = output[:1000]
        lines.append("(No structured fields parsed — showing raw summary)")
        lines.append(raw)
    else:
        labels = {
            "registrar": "Registrar",
            "registrant_name": "Registrant",
            "registrant_org": "Organization",
            "creation_date": "Creation Date",
            "expiry_date": "Expiry Date",
            "updated_date": "Last Updated",
            "name_servers": "Name Servers",
            "status": "Domain Status",
        }
        for key, label in labels.items():
            if key in fields:
                lines.append(f"  {label}: {fields[key]}")

    return "\n".join(lines)


@tool(
    name="suggest_domains",
    description="Suggest alternative domain names based on a keyword (prefixes, suffixes, alternative TLDs).",
    params={
        "keyword": {"type": "string", "description": "Base keyword or name (e.g. 'myproject', 'coolapp')"},
        "tlds": {
            "type": "string",
            "description": "Comma-separated TLDs to check (default: com,net,org,io,dev,app). Set to 'popular' for com/net/org.",
            "default": "com,net,org,io,dev,app",
        },
    },
    required=["keyword"],
)
def suggest_domains(keyword: str, tlds: str = "com,net,org,io,dev,app") -> str:
    """Suggest domain name variations based on a keyword."""
    keyword = keyword.lower().strip()
    # Remove any existing TLD
    keyword = re.sub(r"\.[a-z]{2,}$", "", keyword)
    # Remove non-alphanumeric chars (keep dashes)
    keyword = re.sub(r"[^a-z0-9-]", "", keyword)

    if not keyword:
        return "Please provide a valid keyword."

    if tlds == "popular":
        tld_list = ["com", "net", "org"]
    else:
        tld_list = [t.strip().lstrip(".") for t in tlds.split(",") if t.strip()]

    if not tld_list:
        return "No valid TLDs provided."

    # Generate suggestions
    suggestions = []
    prefixes = ["get", "try", "use", "go", "my", "the", "app"]
    suffixes = ["app", "io", "hub", "lab", "hq", "now", "dev", "api", "cloud"]

    # 1. keyword.tld
    for tld in tld_list:
        suggestions.append(f"  {keyword}.{tld}")

    # 2. keyword{suffix}.tld
    for suffix in suffixes:
        for tld in tld_list[:3]:  # Only com/net/org for variants
            suggestions.append(f"  {keyword}{suffix}.{tld}")

    # 3. {prefix}keyword.tld
    for prefix in prefixes:
        for tld in tld_list[:3]:
            suggestions.append(f"  {prefix}{keyword}.{tld}")

    # 4. keyword-{word}.tld for common words
    for word in ["app", "hq", "io", "co"]:
        for tld in tld_list[:2]:
            suggestions.append(f"  {keyword}-{word}.{tld}")

    lines = [
        f"Domain suggestions for '{keyword}' ({', '.join(tld_list)}):",
        "",
        "Exact matches:",
    ]

    # Add first batch (exact tld matches)
    for s in suggestions[:len(tld_list)]:
        lines.append(s)

    lines.append(f"\nVariations ({len(suggestions) - len(tld_list)} suggestions):")
    batch = suggestions[len(tld_list):len(tld_list) + 20]
    for s in batch:
        lines.append(s)

    if len(suggestions) > len(tld_list) + 20:
        lines.append(f"  ... and {len(suggestions) - len(tld_list) - 20} more")

    lines.append(f"\nTip: Use 'check_domain <domain>' to see if a suggestion is available.")
    return "\n".join(lines)
