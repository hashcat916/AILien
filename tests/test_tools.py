"""Tests for the tools module — registration, shell execution, safety integration."""

import json
import subprocess
from unittest.mock import ANY, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


def test_tools_registry_imports():
    """All tool modules register their tools on import without errors."""
    # Each import triggers @tool decorators that append to TOOLS
    import tools  # noqa: F811
    import tools.mouse  # noqa: F401
    import tools.keyboard  # noqa: F401
    import tools.screen  # noqa: F401
    import tools.shell  # noqa: F401
    import tools.system  # noqa: F401
    import tools.browser  # noqa: F401
    import tools.apps  # noqa: F401
    import tools.files  # noqa: F401

    assert len(tools.TOOLS) > 0, "No tools were registered"
    assert len(tools.list_tools()) > 0, "list_tools() returned empty"


def test_get_tool_returns_callable():
    import tools
    func = tools.get_tool("system_info")
    assert callable(func)


def test_get_tool_nonexistent_raises():
    import tools
    with pytest.raises(KeyError):
        tools.get_tool("nonexistent_tool_xyz")


def test_tool_schema_has_required_fields():
    """Every registered tool has name, description, and parameters."""
    import tools

    for schema in tools.TOOLS:
        fn = schema.get("function", {})
        assert fn.get("name"), f"Tool missing name: {fn}"
        assert fn.get("description"), f"Tool missing description: {fn['name']}"
        assert "parameters" in fn, f"Tool missing parameters: {fn['name']}"


# ---------------------------------------------------------------------------
# Shell tool
# ---------------------------------------------------------------------------


@patch("tools.shell.subprocess.run")
def test_run_shell_success(mock_run):
    from tools.shell import run_shell

    mock_result = MagicMock()
    mock_result.stdout = "hello world\n"
    mock_result.stderr = ""
    mock_result.returncode = 0
    mock_run.return_value = mock_result

    result = run_shell("echo hello")
    assert "hello world" in result
    mock_run.assert_called_once_with(
        "echo hello",
        shell=True,
        capture_output=True,
        text=True,
        timeout=30,
        cwd=None,
    )


@patch("tools.shell.subprocess.run")
def test_run_shell_with_stderr(mock_run):
    from tools.shell import run_shell

    mock_result = MagicMock()
    mock_result.stdout = "output"
    mock_result.stderr = "warning: something"
    mock_result.returncode = 0
    mock_run.return_value = mock_result

    result = run_shell("cmd")
    assert "[stderr]" in result
    assert "warning" in result


@patch("tools.shell.subprocess.run")
def test_run_shell_nonzero_exit(mock_run):
    from tools.shell import run_shell

    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.stderr = "error occurred"
    mock_result.returncode = 1
    mock_run.return_value = mock_result

    result = run_shell("false")
    assert "[exit code 1]" in result


@patch("tools.shell.subprocess.run")
def test_run_shell_timeout(mock_run):
    from tools.shell import run_shell

    mock_run.side_effect = subprocess.TimeoutExpired(cmd="sleep", timeout=5)

    result = run_shell("sleep 100", timeout=5)
    assert "timed out" in result.lower()


@patch("tools.shell.subprocess.run")
def test_run_shell_truncates_long_output(mock_run):
    from tools.shell import run_shell

    mock_result = MagicMock()
    mock_result.stdout = "\n".join(f"line {i}" for i in range(200))
    mock_result.stderr = ""
    mock_result.returncode = 0
    mock_run.return_value = mock_result

    result = run_shell("long command")
    lines = result.splitlines()
    assert len(lines) <= 102  # 100 lines + truncation message


@patch("tools.shell.subprocess.run")
def test_run_shell_with_cwd(mock_run):
    from tools.shell import run_shell

    mock_result = MagicMock()
    mock_result.stdout = "ok"
    mock_result.stderr = ""
    mock_result.returncode = 0
    mock_run.return_value = mock_result

    run_shell("pwd", cwd="/tmp")
    assert mock_run.call_args[1]["cwd"] == "/tmp"


# ---------------------------------------------------------------------------
# Browser text extraction (unit tests — no network)
# ---------------------------------------------------------------------------


@patch("tools.browser.requests.get")
def test_get_webpage_text_basic(mock_get):
    from tools.browser import get_webpage_text

    mock_response = MagicMock()
    mock_response.text = "<html><head><title>Test Page</title></head><body><p>Hello world</p></body></html>"
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    result = get_webpage_text("https://example.com")
    assert "Test Page" in result
    assert "Hello world" in result


@patch("tools.browser.requests.get")
def test_get_webpage_text_rejects_non_http(mock_get):
    from tools.browser import get_webpage_text

    result = get_webpage_text("ftp://files.example.com")
    assert "refused" in result.lower()
    mock_get.assert_not_called()


@patch("tools.browser.requests.get")
def test_get_webpage_text_auto_adds_scheme(mock_get):
    from tools.browser import get_webpage_text

    mock_response = MagicMock()
    mock_response.text = "<html><title>OK</title><body>content</body></html>"
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    result = get_webpage_text("example.com")
    assert "OK" in result
    # Should have prepended https://
    called_url = mock_get.call_args[0][0]
    assert called_url.startswith("https://")


# ---------------------------------------------------------------------------
# System info
# ---------------------------------------------------------------------------


@patch("tools.system.psutil")
def test_system_info_returns_string(mock_psutil):
    """system_info() should return a non-empty string with expected fields."""
    from tools.system import system_info

    # Mock psutil values
    mock_mem = MagicMock()
    mock_mem.percent = 45.0
    mock_mem.used = 8 * 1024**3
    mock_mem.total = 16 * 1024**3
    mock_psutil.virtual_memory.return_value = mock_mem

    mock_disk = MagicMock()
    mock_disk.used = 200 * 1024**3
    mock_disk.total = 500 * 1024**3
    mock_psutil.disk_usage.return_value = mock_disk

    mock_psutil.boot_time.return_value = 1000000.0
    mock_psutil.cpu_percent.return_value = 30.0
    mock_psutil.cpu_count.return_value = 8

    result = system_info()
    assert isinstance(result, str)
    assert len(result) > 20
    assert "CPU" in result
    assert "Memory" in result
    assert "Disk" in result


# ---------------------------------------------------------------------------
# Safety guard integration in tool execution
# ---------------------------------------------------------------------------


@patch("tools.shell.subprocess.run")
def test_tool_decorator_registers_correctly(mock_run):
    """Verify that the @tool decorator produces valid OpenAI-compatible schemas."""
    import tools

    for schema in tools.TOOLS:
        fn = schema.get("function", {})
        params = fn.get("parameters", {})
        assert params.get("type") == "object", f"Tool {fn['name']} params type not 'object'"
        assert isinstance(params.get("properties"), dict), f"Tool {fn['name']} missing properties"
        assert isinstance(params.get("required", []), list), f"Tool {fn['name']} required not a list"


# ---------------------------------------------------------------------------
# Open URL validation
# ---------------------------------------------------------------------------


@patch("tools.browser.webbrowser.open")
def test_open_url_adds_scheme(mock_webopen):
    from tools.browser import open_url
    result = open_url("google.com")
    assert "google.com" in result
    # Should have been called with https://google.com
    called_url = mock_webopen.call_args[0][0]
    assert called_url.startswith("https://")


@patch("tools.browser.webbrowser.open")
def test_open_url_rejects_non_http(mock_webopen):
    from tools.browser import open_url
    result = open_url("javascript:alert(1)")
    assert "refused" in result.lower()
    mock_webopen.assert_not_called()
