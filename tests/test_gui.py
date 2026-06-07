"""Tests for GUI components — icon creation, darken_color, and basic tray/control panel instantiation."""

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _create_emoji_icon
# ---------------------------------------------------------------------------


def test_create_emoji_icon_basic():
    """_create_emoji_icon should return a PIL Image."""
    from gui.tray import _create_emoji_icon

    img = _create_emoji_icon(64)
    assert img is not None
    assert img.size == (64, 64)
    assert img.mode == "RGBA"


def test_create_emoji_icon_custom_size():
    from gui.tray import _create_emoji_icon

    img = _create_emoji_icon(128)
    assert img.size == (128, 128)


def test_create_emoji_icon_custom_color():
    from gui.tray import _create_emoji_icon

    img = _create_emoji_icon(64, accent_color=(74, 222, 128, 255))
    assert img is not None
    assert img.size == (64, 64)


def test_create_emoji_icon_without_icon_file():
    """Should still create an icon even if the alien PNG doesn't exist."""
    from gui.tray import _create_emoji_icon

    # The function catches exceptions silently when loading the icon
    img = _create_emoji_icon(64)
    assert img is not None


# ---------------------------------------------------------------------------
# _darken_color
# ---------------------------------------------------------------------------


def test_darken_color_default_factor():
    from gui.tray import _darken_color

    result = _darken_color((100, 150, 200, 255))
    assert len(result) == 4
    # All channels should be darkened
    assert result[0] < 100
    assert result[1] < 150
    assert result[2] < 200
    assert result[3] == 255  # Alpha unchanged


def test_darken_color_custom_factor():
    from gui.tray import _darken_color

    result = _darken_color((200, 200, 200, 255), factor=0.5)
    assert result == (100, 100, 100, 255)


def test_darken_color_no_change():
    from gui.tray import _darken_color

    result = _darken_color((100, 100, 100, 255), factor=1.0)
    assert result == (100, 100, 100, 255)


# ---------------------------------------------------------------------------
# TrayIcon (unit tests — mocked display)
# ---------------------------------------------------------------------------


@patch("gui.tray.TrayIcon._init_control_panel")
def test_tray_icon_init(mock_cp):
    """TrayIcon should initialize without errors."""
    from gui.tray import TrayIcon

    tray = TrayIcon()
    assert tray._status == "idle"
    assert tray._stop_event is not None
    assert mock_cp.called


@patch("gui.tray.TrayIcon._init_control_panel")
def test_tray_icon_put_status(mock_cp):
    from gui.tray import TrayIcon

    tray = TrayIcon()
    # Should not raise — no icon yet (not started)
    tray.put_status("listening")
    assert tray._status == "listening"


# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------


def test_tray_status_labels():
    from gui.tray import STATUS_LABELS

    assert STATUS_LABELS["idle"] == "Idle"
    assert STATUS_LABELS["listening"] == "Listening..."
    assert STATUS_LABELS["thinking"] == "Thinking..."
    assert STATUS_LABELS["speaking"] == "Speaking..."


def test_tray_status_colors():
    from gui.tray import STATUS_COLORS

    assert len(STATUS_COLORS["idle"]) == 4  # RGBA
    assert len(STATUS_COLORS["listening"]) == 4
    assert len(STATUS_COLORS["thinking"]) == 4
    assert len(STATUS_COLORS["speaking"]) == 4


# ---------------------------------------------------------------------------
# ControlPanel constants
# ---------------------------------------------------------------------------


def test_control_panel_status_colors():
    from gui.control_panel import STATUS_COLORS, STATUS_LABELS

    assert STATUS_COLORS["idle"] == "#808080"
    assert STATUS_COLORS["listening"] == "#4ade80"
    assert STATUS_COLORS["thinking"] == "#fbbf24"
    assert STATUS_COLORS["speaking"] == "#60a5fa"

    assert STATUS_LABELS["idle"] == "Idle"
    assert STATUS_LABELS["listening"] == "Listening..."
    assert STATUS_LABELS["thinking"] == "Thinking..."
    assert STATUS_LABELS["speaking"] == "Speaking..."
