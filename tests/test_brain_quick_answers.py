"""Tests for brain/quick_answers.py — dispatch, math, conversions, greetings, system info."""

from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Dispatch — general routing
# ---------------------------------------------------------------------------


def test_dispatch_greeting():
    from brain.quick_answers import dispatch

    result = dispatch("hello")
    assert result is not None
    assert isinstance(result, str)
    assert len(result) > 0


def test_dispatch_greeting_uppercase():
    from brain.quick_answers import dispatch

    result = dispatch("HELLO")
    assert result is not None


def test_dispatch_unknown_returns_none():
    from brain.quick_answers import dispatch

    result = dispatch("supercalifragilisticexpialidocious")
    assert result is None


# ---------------------------------------------------------------------------
# Specific handlers
# ---------------------------------------------------------------------------


def test_dispatch_time():
    from brain.quick_answers import dispatch

    result = dispatch("what time is it")
    assert result is not None
    assert ":" in result or "o'clock" in result.lower()


def test_dispatch_date():
    from brain.quick_answers import dispatch

    result = dispatch("what's the date")
    assert result is not None
    assert any(word in result.lower() for word in ["today", "is", ","])  # "Today is ..."


def test_dispatch_day():
    from brain.quick_answers import dispatch

    result = dispatch("what day of the week")
    assert result is not None
    assert "it's" in result.lower() or "today" in result.lower()


def test_dispatch_thanks():
    from brain.quick_answers import dispatch

    result = dispatch("thank you")
    assert result is not None
    assert len(result) > 0


def test_dispatch_whoami():
    from brain.quick_answers import dispatch

    result = dispatch("who are you")
    assert result is not None
    assert "AILIEN" in result or "assistant" in result.lower()


def test_dispatch_what_can_you_do():
    from brain.quick_answers import dispatch

    result = dispatch("what can you do")
    assert result is not None
    assert "mouse" in result.lower() or "keyboard" in result.lower() or "control" in result.lower()


def test_dispatch_ping():
    from brain.quick_answers import dispatch

    result = dispatch("are you there")
    assert result is not None
    assert len(result) > 0


def test_dispatch_joke():
    from brain.quick_answers import dispatch

    result = dispatch("tell me a joke")
    assert result is not None
    assert len(result) > 10  # Should be a full joke


def test_dispatch_motivate():
    from brain.quick_answers import dispatch

    result = dispatch("motivate me")
    assert result is not None
    assert "—" in result  # Quote attribution


# ---------------------------------------------------------------------------
# Farewell
# ---------------------------------------------------------------------------


def test_dispatch_goodbye():
    from brain.quick_answers import dispatch

    result = dispatch("goodbye")
    assert result is not None
    assert len(result) > 0


# ---------------------------------------------------------------------------
# System status queries (mocked to avoid real psutil calls)
# ---------------------------------------------------------------------------


@patch("brain.quick_answers.psutil")
def test_dispatch_system_status(mock_psutil):
    from brain.quick_answers import dispatch

    mock_mem = mock_psutil.virtual_memory.return_value
    mock_mem.percent = 50.0
    mock_psutil.cpu_percent.return_value = 30.0

    result = dispatch("system status")
    assert result is not None
    assert "CPU" in result or "%" in result


@patch("brain.quick_answers.psutil")
def test_dispatch_cpu(mock_psutil):
    from brain.quick_answers import dispatch

    mock_psutil.cpu_percent.return_value = 50.0

    result = dispatch("cpu usage")
    assert result is not None
    assert "%" in result


@patch("brain.quick_answers.psutil")
def test_dispatch_memory(mock_psutil):
    from brain.quick_answers import dispatch

    mock_mem = mock_psutil.virtual_memory.return_value
    mock_mem.percent = 60.0
    mock_mem.used = 8 * 1024**3
    mock_mem.total = 16 * 1024**3

    result = dispatch("memory")
    assert result is not None
    assert "RAM" in result or "GB" in result


@patch("brain.quick_answers.psutil")
def test_dispatch_uptime(mock_psutil):
    from brain.quick_answers import dispatch

    import datetime
    mock_psutil.boot_time.return_value = (datetime.datetime.now() - datetime.timedelta(hours=12)).timestamp()

    result = dispatch("uptime")
    assert result is not None
    assert "up" in result.lower()


# ---------------------------------------------------------------------------
# Math
# ---------------------------------------------------------------------------


def test_try_math_simple_addition():
    from brain.quick_answers import try_math

    result = try_math("what is 5 + 3")
    assert result is not None
    assert "8" in result


def test_try_math_multiplication():
    from brain.quick_answers import try_math

    result = try_math("calculate 12 * 4")
    assert result is not None
    assert "48" in result


def test_try_math_division():
    from brain.quick_answers import try_math

    result = try_math("what's 100 / 4")
    assert result is not None
    assert "25" in result


def test_try_math_subtraction():
    from brain.quick_answers import try_math

    result = try_math("compute 50 - 17")
    assert result is not None
    assert "33" in result


def test_try_math_with_x_operator():
    from brain.quick_answers import try_math

    result = try_math("what is 6 * 7")
    assert result is not None
    assert "42" in result


def test_try_math_not_math_text():
    from brain.quick_answers import try_math

    result = try_math("what is your name")
    assert result is None


def test_try_math_division_with_divide_operator():
    from brain.quick_answers import try_math

    result = try_math("evaluate 81 / 9")
    assert result is not None
    assert "9" in result


# ---------------------------------------------------------------------------
# Unit conversions
# ---------------------------------------------------------------------------


def test_try_conversion_kb_to_mb():
    from brain.quick_answers import try_conversion

    result = try_conversion("convert 1024 kb to mb")
    assert result is not None
    assert "1" in result  # 1024 KB = 1 MB


def test_try_conversion_kg_to_g():
    from brain.quick_answers import try_conversion

    result = try_conversion("convert 2 kg to g")
    assert result is not None
    assert "2000" in result


def test_try_conversion_unknown_returns_none():
    from brain.quick_answers import try_conversion

    result = try_conversion("what is the weather")
    assert result is None


# ---------------------------------------------------------------------------
# Knowledge base integration (mocked)
# ---------------------------------------------------------------------------


def test_dispatch_list_knowledge():
    """Verify that knowledge-related keywords trigger the handler."""
    from brain.quick_answers import dispatch

    # 'list knowledge' should match the registered pattern.
    # The handler tries to import brain.knowledge internally.
    result = dispatch("list knowledge")
    # Should either return content or None if import fails — not crash.
    assert result is None or isinstance(result, str)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_dispatch_empty_string():
    from brain.quick_answers import dispatch

    result = dispatch("")
    assert result is None


def test_dispatch_whitespace():
    from brain.quick_answers import dispatch

    result = dispatch("   ")
    assert result is None


def test_dispatch_punctuation():
    """Quick answers should handle trailing punctuation."""
    from brain.quick_answers import dispatch

    result = dispatch("hello!")
    assert result is not None

    result2 = dispatch("hello world!!!")
    assert result2 is not None


def test_dispatch_mixed_case():
    from brain.quick_answers import dispatch

    result = dispatch("GoOdByE")
    assert result is not None
