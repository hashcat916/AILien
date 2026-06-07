"""Tests for brain/proactive.py — monitor start/stop, alert states, cooldowns."""

import time
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _AlertState
# ---------------------------------------------------------------------------


def test_alert_state_defaults():
    from brain.proactive import _AlertState

    state = _AlertState()
    assert state.last_fired == 0.0
    assert state.last_value == 0.0


def test_alert_state_cooldown_active():
    from brain.proactive import _AlertState

    state = _AlertState()
    state.last_fired = time.time()  # Just now
    assert state.is_on_cooldown(60) is True  # Should still be on cooldown


def test_alert_state_cooldown_expired():
    from brain.proactive import _AlertState

    state = _AlertState()
    state.last_fired = time.time() - 120  # 2 minutes ago
    assert state.is_on_cooldown(60) is False  # 60s cooldown has expired


def test_alert_state_custom_cooldown():
    from brain.proactive import _AlertState

    state = _AlertState()
    state.last_fired = time.time() - 30
    assert state.is_on_cooldown(300) is True  # 5 min cooldown, 30s ago
    assert state.is_on_cooldown(10) is False  # 10s cooldown, 30s ago


# ---------------------------------------------------------------------------
# ProactiveMonitor
# ---------------------------------------------------------------------------


def test_monitor_start_stop():
    from brain.proactive import ProactiveMonitor

    monitor = ProactiveMonitor()
    assert monitor._running is False

    monitor.start()
    assert monitor._running is True
    assert monitor._thread is not None
    assert monitor._thread.is_alive()

    monitor.stop()
    assert monitor._running is False


def test_monitor_alert_callback():
    from brain.proactive import ProactiveMonitor

    callback = MagicMock()
    monitor = ProactiveMonitor(alert_callback=callback)
    monitor._alert("Test alert")
    callback.assert_called_once_with("Test alert")


def test_monitor_alert_no_callback():
    from brain.proactive import ProactiveMonitor

    monitor = ProactiveMonitor()  # No callback
    # Should not raise
    monitor._alert("Test alert")


@patch("brain.proactive.ProactiveMonitor._check_battery")
@patch("brain.proactive.ProactiveMonitor._check_cpu")
@patch("brain.proactive.ProactiveMonitor._check_memory")
@patch("brain.proactive.ProactiveMonitor._check_disk")
def test_monitor_loop_calls_all_checks(mock_disk, mock_memory, mock_cpu, mock_battery):
    """The monitor loop should call all check methods."""
    from brain.proactive import ProactiveMonitor
    import brain.proactive as bp

    monitor = ProactiveMonitor()
    monitor._running = True

    def fake_sleep(duration):
        monitor._running = False  # Exit after one iteration

    with patch.object(bp.time, "sleep", side_effect=fake_sleep):
        monitor._monitor_loop()

    assert mock_battery.called
    assert mock_cpu.called
    assert mock_memory.called
    assert mock_disk.called


# ---------------------------------------------------------------------------
# Individual check methods
# ---------------------------------------------------------------------------


def _make_battery_capacity(level: int):
    """Create a mock capacity file-like object."""
    mock_cap = MagicMock()
    mock_cap.read_text.return_value = str(level)
    return mock_cap


@patch("brain.proactive.Path")
def test_check_battery_low(mock_path_cls):
    from brain.proactive import ProactiveMonitor

    callback = MagicMock()
    monitor = ProactiveMonitor(alert_callback=callback)

    mock_cap = _make_battery_capacity(15)
    # Mock Path('/sys/class/power_supply').glob('*/capacity')
    mock_path = MagicMock()
    mock_path_cls.return_value = mock_path
    mock_path.glob.return_value = [mock_cap]

    monitor._check_battery()
    assert callback.called


@patch("brain.proactive.Path")
def test_check_battery_critical(mock_path_cls):
    from brain.proactive import ProactiveMonitor

    callback = MagicMock()
    monitor = ProactiveMonitor(alert_callback=callback)

    mock_cap = _make_battery_capacity(5)
    mock_path = MagicMock()
    mock_path_cls.return_value = mock_path
    mock_path.glob.return_value = [mock_cap]

    monitor._check_battery()
    assert callback.called
    msg = callback.call_args[0][0]
    assert "critically" in msg.lower() or "warning" in msg.lower()


def test_check_battery_no_battery():
    """Should silently handle missing battery."""
    from brain.proactive import ProactiveMonitor

    callback = MagicMock()
    monitor = ProactiveMonitor(alert_callback=callback)

    with patch("brain.proactive.Path.glob", return_value=[]):
        monitor._check_battery()
        assert not callback.called


@patch("brain.proactive.psutil")
def test_check_cpu_high(mock_psutil):
    from brain.proactive import ProactiveMonitor

    callback = MagicMock()
    monitor = ProactiveMonitor(alert_callback=callback)

    mock_psutil.cpu_percent.return_value = 95.0

    monitor._check_cpu()
    assert callback.called
    msg = callback.call_args[0][0]
    assert "CPU" in msg


@patch("brain.proactive.psutil")
def test_check_cpu_normal(mock_psutil):
    from brain.proactive import ProactiveMonitor

    callback = MagicMock()
    monitor = ProactiveMonitor(alert_callback=callback)

    mock_psutil.cpu_percent.return_value = 30.0

    monitor._check_cpu()
    assert not callback.called  # Below threshold


@patch("brain.proactive.psutil")
def test_check_memory_high(mock_psutil):
    from brain.proactive import ProactiveMonitor

    callback = MagicMock()
    monitor = ProactiveMonitor(alert_callback=callback)

    mock_mem = mock_psutil.virtual_memory.return_value
    mock_mem.percent = 95.0
    mock_mem.used = 15 * 1024**3
    mock_mem.total = 16 * 1024**3

    monitor._check_memory()
    assert callback.called
    msg = callback.call_args[0][0]
    assert "Memory" in msg


@patch("brain.proactive.psutil")
def test_check_memory_normal(mock_psutil):
    from brain.proactive import ProactiveMonitor

    callback = MagicMock()
    monitor = ProactiveMonitor(alert_callback=callback)

    mock_mem = mock_psutil.virtual_memory.return_value
    mock_mem.percent = 50.0

    monitor._check_memory()
    assert not callback.called  # Below threshold


@patch("brain.proactive.psutil")
def test_check_disk_full(mock_psutil):
    from brain.proactive import ProactiveMonitor

    callback = MagicMock()
    monitor = ProactiveMonitor(alert_callback=callback)

    mock_disk = mock_psutil.disk_usage.return_value
    mock_disk.percent = 96.0
    mock_disk.free = 5 * 1024**3

    monitor._check_disk()
    assert callback.called
    msg = callback.call_args[0][0]
    assert "Disk" in msg or "space" in msg.lower()


@patch("brain.proactive.psutil")
def test_check_disk_normal(mock_psutil):
    from brain.proactive import ProactiveMonitor

    callback = MagicMock()
    monitor = ProactiveMonitor(alert_callback=callback)

    mock_disk = mock_psutil.disk_usage.return_value
    mock_disk.percent = 50.0
    mock_disk.free = 100 * 1024**3

    monitor._check_disk()
    assert not callback.called


# ---------------------------------------------------------------------------
# Cooldown enforcement
# ---------------------------------------------------------------------------


@patch("brain.proactive.Path")
@patch("brain.proactive.ProactiveMonitor._alert")
def test_battery_alert_cooldown(mock_alert, mock_path_cls):
    """Battery alerts should respect cooldown periods."""
    from brain.proactive import ProactiveMonitor

    monitor = ProactiveMonitor()

    mock_cap = _make_battery_capacity(15)
    mock_path = MagicMock()
    mock_path_cls.return_value = mock_path
    mock_path.glob.return_value = [mock_cap]

    # First call should fire
    monitor._check_battery()
    assert mock_alert.called

    # Reset, then call again immediately — should be on cooldown
    mock_alert.reset_mock()
    monitor._check_battery()
    assert not mock_alert.called  # Cooldown active
