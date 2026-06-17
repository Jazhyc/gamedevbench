"""Tests for the cross-platform screenshot MCP server.

mss is mocked so these run headless in CI (no real monitor required). Guards
the Windows/macOS/Linux capture path and the out-of-range monitor fallback.
"""
import base64
from io import BytesIO

from PIL import Image

from gamedevbench.src import mcp_server


class _FakeShot:
    def __init__(self, width, height):
        self.size = (width, height)
        self.rgb = b"\x12\x34\x56" * (width * height)


class _FakeMSS:
    def __init__(self, monitors):
        self._monitors = monitors
        self.grabbed = None

    @property
    def monitors(self):
        return self._monitors

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def grab(self, mon):
        self.grabbed = mon
        return _FakeShot(mon["width"], mon["height"])


def _install_fake_mss(monkeypatch, widths):
    # monitors[0] is the combined virtual screen; the rest are real monitors.
    monitors = [{"left": 0, "top": 0, "width": 999, "height": 2}]
    monitors += [{"left": 0, "top": 0, "width": w, "height": 2} for w in widths]
    monkeypatch.setattr(mcp_server.mss, "MSS", lambda: _FakeMSS(monitors))


def _png_width(png: bytes) -> int:
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    return Image.open(BytesIO(png)).size[0]


def test_capture_selects_requested_monitor(monkeypatch):
    _install_fake_mss(monkeypatch, widths=[11, 22])
    assert _png_width(mcp_server.capture_display(2)) == 22


def test_capture_out_of_range_falls_back_to_primary(monkeypatch):
    _install_fake_mss(monkeypatch, widths=[11, 22])
    assert _png_width(mcp_server.capture_display(99)) == 11  # monitor 1 = primary


def test_capture_non_positive_falls_back_to_primary(monkeypatch):
    _install_fake_mss(monkeypatch, widths=[11, 22])
    assert _png_width(mcp_server.capture_display(0)) == 11


def test_compress_screenshot_stays_under_budget():
    img = Image.new("RGB", (1280, 720), (40, 80, 120))
    buf = BytesIO()
    img.save(buf, format="PNG")
    comp, mime = mcp_server.compress_screenshot(buf.getvalue())
    assert mime == "image/jpeg"
    b64_kb = len(base64.b64encode(comp)) / 1024
    assert b64_kb <= mcp_server.MAX_TARGET_SIZE_KB
