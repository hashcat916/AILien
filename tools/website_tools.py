"""Website development and serving tools."""
import os
import socket
import subprocess
import threading
import time
from pathlib import Path

from tools import tool

# Track background web servers
_ACTIVE_SERVERS: dict[int, dict] = {}
_server_lock = threading.Lock()


def _find_free_port(start: int = 8000, end: int = 9000) -> int:
    """Find a free port in the given range."""
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return 0


@tool(
    name="serve_directory",
    description="Start a local HTTP server to serve files from a directory. Opens the URL in the browser.",
    params={
        "directory": {
            "type": "string",
            "description": "Directory to serve (default: current directory)",
            "default": ".",
        },
        "port": {
            "type": "integer",
            "description": "Port to serve on (default: auto-pick a free port)",
            "default": 0,
        },
        "open_browser": {
            "type": "boolean",
            "description": "Open the server URL in the browser (default: true)",
            "default": True,
        },
    },
    required=[],
)
def serve_directory(directory: str = ".", port: int = 0, open_browser: bool = True) -> str:
    """Start a local HTTP server for a directory."""
    import config as _config

    try:
        p = Path(directory).expanduser().resolve()
        if not p.is_dir():
            return f"Directory does not exist: {p}"

        if port == 0:
            port = _find_free_port()
            if port == 0:
                return "Could not find a free port."

        # Start the HTTP server in a background thread
        httpd = None
        server_ready = threading.Event()
        server_error = []

        def _serve():
            nonlocal httpd
            try:
                os.chdir(str(p))
                handler = __import__("http.server").SimpleHTTPRequestHandler

                class _QuietHandler(handler):
                    def log_message(self, fmt, *args):
                        pass  # Suppress request logs

                httpd = __import__("http.server").HTTPServer(("127.0.0.1", port), _QuietHandler)
                server_ready.set()
                httpd.serve_forever()
            except Exception as exc:
                server_error.append(str(exc))
                server_ready.set()

        t = threading.Thread(target=_serve, daemon=True)
        t.start()
        server_ready.wait(timeout=3)

        if server_error:
            return f"Failed to start server: {server_error[0]}"

        url = f"http://127.0.0.1:{port}"

        with _server_lock:
            _ACTIVE_SERVERS[port] = {
                "directory": str(p),
                "url": url,
                "started": time.strftime("%H:%M:%S"),
                "thread": t,
            }

        if open_browser:
            subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        lines = [
            f"Serving directory: {p}",
            f"URL: {url}",
            f"Press Ctrl+C in the terminal to stop.",
        ]
        if _ACTIVE_SERVERS:
            active = [f"  {v['url']}  ({v['directory']})" for v in _ACTIVE_SERVERS.values()]
            lines.append(f"\nActive servers ({len(_ACTIVE_SERVERS)}):")
            lines.extend(active)

        return "\n".join(lines)

    except Exception as e:
        return f"Error starting server: {e}"


@tool(
    name="stop_server",
    description="Stop a running local HTTP server by port number.",
    params={
        "port": {
            "type": "integer",
            "description": "Port number of the server to stop (e.g. 8000)",
        },
    },
    required=["port"],
)
def stop_server(port: int) -> str:
    """Stop a running HTTP server by its port."""
    with _server_lock:
        if port not in _ACTIVE_SERVERS:
            return f"No active server found on port {port}."

        # Shutdown the server by connecting and sending a request
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            s.connect(("127.0.0.1", port))
            s.sendall(b"GET / HTTP/1.0\r\n\r\n")
            s.close()
        except Exception:
            pass

        info = _ACTIVE_SERVERS.pop(port)
        return f"Stopped server on port {port} ({info['directory']})."


@tool(
    name="list_servers",
    description="List all running local HTTP servers.",
    params={},
    required=[],
)
def list_servers() -> str:
    """List all active local HTTP servers."""
    with _server_lock:
        if not _ACTIVE_SERVERS:
            return "No active servers."

        lines = [f"Active servers ({len(_ACTIVE_SERVERS)}):"]
        for port, info in sorted(_ACTIVE_SERVERS.items()):
            lines.append(f"  Port {port}: {info['url']}  → {info['directory']}  (since {info['started']})")
        return "\n".join(lines)


@tool(
    name="scaffold_website",
    description="Create a basic HTML/CSS/JS website scaffold in a directory.",
    params={
        "name": {
            "type": "string",
            "description": "Project name (will create a subdirectory with this name)",
        },
        "directory": {
            "type": "string",
            "description": "Parent directory (default: current)",
            "default": ".",
        },
        "framework": {
            "type": "string",
            "description": "Type of scaffold: 'basic' (HTML+CSS+JS), 'tailwind' (CDN), 'bootstrap' (CDN), 'full' (multi-page structure). Default: basic",
            "default": "basic",
        },
    },
    required=["name"],
)
def scaffold_website(name: str, directory: str = ".", framework: str = "basic") -> str:
    """Create a basic website scaffold."""
    try:
        parent = Path(directory).expanduser().resolve()
        project_dir = parent / name

        if project_dir.exists():
            return f"Directory already exists: {project_dir}"

        project_dir.mkdir(parents=True, exist_ok=True)
        project_name = name
        year = time.strftime("%Y")

        framework = framework.lower()

        if framework == "basic":
            html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project_name}</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <h1>Welcome to {project_name}</h1>
    <p>Your project is ready. Edit the files to get started.</p>
    <script src="script.js"></script>
</body>
</html>
'''
            (project_dir / "index.html").write_text(html)

            css = f'''/* {project_name} — Styles */
* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, sans-serif;
    line-height: 1.6;
    color: #333;
    max-width: 800px;
    margin: 0 auto;
    padding: 2rem;
    background: #fafafa;
}}

h1 {{
    color: #1a1a1a;
    margin-bottom: 1rem;
}}

p {{
    color: #666;
}}
'''
            (project_dir / "style.css").write_text(css)

            js = f'''// {project_name} — Scripts
console.log("{project_name} loaded!");
'''
            (project_dir / "script.js").write_text(js)

        elif framework == "tailwind":
            html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project_name}</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 min-h-screen flex items-center justify-center">
    <div class="text-center">
        <h1 class="text-4xl font-bold text-gray-900 mb-4">{project_name}</h1>
        <p class="text-lg text-gray-600">Built with Tailwind CSS</p>
    </div>
</body>
</html>
'''
            (project_dir / "index.html").write_text(html)

        elif framework == "bootstrap":
            html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project_name}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <div class="container text-center mt-5">
        <h1 class="display-4">{project_name}</h1>
        <p class="lead">Built with Bootstrap 5</p>
    </div>
</body>
</html>
'''
            (project_dir / "index.html").write_text(html)

        elif framework == "full":
            # Multi-page structure
            html_idx = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project_name}</title>
    <link rel="stylesheet" href="css/style.css">
</head>
<body>
    <header>
        <nav>
            <a href="index.html">Home</a>
            <a href="about.html">About</a>
            <a href="contact.html">Contact</a>
        </nav>
    </header>
    <main>
        <h1>Welcome to {project_name}</h1>
        <p>This is a multi-page website scaffold.</p>
    </main>
    <footer>
        <p>&copy; {year} {project_name}</p>
    </footer>
    <script src="js/main.js"></script>
</body>
</html>
'''
            (project_dir / "index.html").write_text(html_idx)

            html_about = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>About — {project_name}</title>
    <link rel="stylesheet" href="css/style.css">
</head>
<body>
    <header>
        <nav>
            <a href="index.html">Home</a>
            <a href="about.html">About</a>
            <a href="contact.html">Contact</a>
        </nav>
    </header>
    <main>
        <h1>About</h1>
        <p>About page content goes here.</p>
    </main>
</body>
</html>
'''
            (project_dir / "about.html").write_text(html_about)

            html_contact = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Contact — {project_name}</title>
    <link rel="stylesheet" href="css/style.css">
</head>
<body>
    <header>
        <nav>
            <a href="index.html">Home</a>
            <a href="about.html">About</a>
            <a href="contact.html">Contact</a>
        </nav>
    </header>
    <main>
        <h1>Contact</h1>
        <p>Contact page content goes here.</p>
    </main>
</body>
</html>
'''
            (project_dir / "contact.html").write_text(html_contact)

            (project_dir / "css").mkdir(exist_ok=True)
            css = f'''/* {project_name} — Styles */
* {{ margin: 0; padding: 0; box-sizing: border-box; }}

body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    line-height: 1.6;
    color: #333;
}}

header {{
    background: #1a1a1a;
    padding: 1rem 2rem;
}}

nav a {{
    color: #fff;
    text-decoration: none;
    margin-right: 1.5rem;
    font-size: 1.1rem;
}}

nav a:hover {{ color: #4dabf7; }}

main {{
    max-width: 800px;
    margin: 2rem auto;
    padding: 0 2rem;
}}

h1 {{ margin-bottom: 1rem; color: #1a1a1a; }}

footer {{
    text-align: center;
    padding: 2rem;
    color: #888;
    font-size: 0.9rem;
}}
'''
            (project_dir / "css/style.css").write_text(css)

            (project_dir / "js").mkdir(exist_ok=True)
            js = f'''// {project_name} — Main scripts
console.log("{project_name} loaded!");
'''
            (project_dir / "js/main.js").write_text(js)

        else:
            return f"Unknown framework '{framework}'. Use: basic, tailwind, bootstrap, or full."

        # Summary
        files = sorted(f.relative_to(project_dir) for f in project_dir.rglob("*") if f.is_file())
        lines = [
            f"Created website scaffold: {project_dir}",
            f"Framework: {framework}",
            f"Files ({len(files)}):",
        ]
        for f in files:
            size = (project_dir / f).stat().st_size
            lines.append(f"  {f}  ({size} bytes)")

        lines.append(f"\nTip: Run 'serve_directory {project_dir}' to preview in your browser.")
        return "\n".join(lines)

    except Exception as e:
        return f"Error creating scaffold: {e}"
