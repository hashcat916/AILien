"""Email tools — compose and send emails via browser or mailto links."""
import subprocess
import webbrowser
from urllib.parse import quote

from tools import tool


@tool(
    name="compose_email",
    description="Open the default email client with a pre-filled draft. Use this to write and send emails.",
    params={
        "to": {"type": "string", "description": "Recipient email address", "default": ""},
        "subject": {"type": "string", "description": "Email subject line", "default": ""},
        "body": {"type": "string", "description": "Email body content", "default": ""},
        "cc": {"type": "string", "description": "CC recipient (optional)", "default": ""},
    },
    required=[],
)
def compose_email(to: str = "", subject: str = "", body: str = "", cc: str = "") -> str:
    """Open the default email client with a pre-filled draft using a mailto: link."""
    # Build mailto: URI
    parts = [f"mailto:{quote(to)}"]
    params = []
    if subject:
        params.append(f"subject={quote(subject)}")
    if body:
        params.append(f"body={quote(body)}")
    if cc:
        params.append(f"cc={quote(cc)}")
    if params:
        parts.append("?" + "&".join(params))

    uri = "".join(parts)

    try:
        webbrowser.open(uri)
        return f"Opened email draft to {to or '(no recipient)'}."
    except Exception as e:
        return f"Failed to open email: {e}"
