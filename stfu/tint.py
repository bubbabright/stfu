# stfu/tint.py — click-through black tint overlay + HTTP control
"""Fullscreen click-through black veil for a "night light on steroids"
sleep-tint effect. Uses WS_EX_LAYERED|WS_EX_TRANSPARENT + Tk's own -alpha
for opacity — NOT overlay.py's -transparentcolor "black" trick, which
would make solid black invisible instead of opaque (black is already
overlay.py's magic transparent-color key, so this window can't reuse it).

Runs in the interactive session as its own process (--tint-only) — same
constraint as overlay.py: tkinter needs the desktop, not the registry.
Controlled entirely over HTTP from web.py; the tint window itself never
needs keyboard focus (click-through windows don't reliably receive
keyboard input on Windows anyway).
"""
import ctypes
import json
import logging
import sys
import threading
import tkinter as tk
import urllib.error
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

from flask import Flask, jsonify, request

from stfu.config import acquire_singleton_lock

if TYPE_CHECKING:
    from stfu.config import AppConfig

log = logging.getLogger("stfu.tint")

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020


def _make_click_through(hwnd):
    style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    style |= WS_EX_LAYERED | WS_EX_TRANSPARENT
    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)


def run_tint(config) -> None:
    lock_path = Path(config.log.file).parent / "stfu_tint.lock"
    try:
        acquire_singleton_lock(lock_path)
    except RuntimeError as e:
        log.error(str(e))
        print(str(e))
        sys.exit(1)

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.configure(bg="black")

    w = root.winfo_screenwidth()
    h = root.winfo_screenheight()
    root.geometry(f"{w}x{h}+0+0")

    state = {"alpha": 0.0}
    root.attributes("-alpha", state["alpha"])

    root.update_idletasks()
    hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
    _make_click_through(hwnd)

    def apply_alpha(alpha):
        state["alpha"] = alpha
        root.attributes("-alpha", alpha)

    def _run_control_server():
        app = Flask(__name__)

        @app.route("/status", methods=["GET"])
        def status():
            return jsonify({"active": True, "alpha": state["alpha"]})

        @app.route("/opacity", methods=["POST"])
        def opacity():
            data = request.get_json(silent=True) or {}
            try:
                alpha = float(data.get("alpha"))
            except (TypeError, ValueError):
                return jsonify({"error": "alpha must be a number"}), 400
            alpha = min(config.tint.alpha_max, max(0.0, alpha))
            # tkinter isn't thread-safe — this runs on the Flask request
            # thread, so the actual mutation has to be marshaled onto the
            # Tk mainloop thread via root.after(), never called directly.
            root.after(0, apply_alpha, alpha)
            return jsonify({"active": True, "alpha": alpha})

        log.info("tint control server listening on 0.0.0.0:%d", config.tint.control_port)
        app.run(
            host="0.0.0.0",
            port=config.tint.control_port,
            debug=False,
            use_reloader=False,
            threaded=True,
        )

    threading.Thread(target=_run_control_server, daemon=True).start()

    log.info("Tint overlay started")
    root.mainloop()
    log.info("Tint overlay stopped")


class TintUnavailable(Exception):
    """Raised by HTTPTintClient when the tint process can't be reached."""


class HTTPTintClient:
    """Relays tint requests to the --tint-only process over HTTP.

    Used by every run mode except the tint process itself.
    """

    def __init__(self, config: "AppConfig"):
        self._base = f"http://127.0.0.1:{config.tint.control_port}"
        self._timeout = config.tint.control_timeout

    def status(self) -> dict:
        return self._request("GET", "/status")

    def set_opacity(self, alpha: float) -> dict:
        return self._request("POST", "/opacity", {"alpha": alpha})

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            f"{self._base}{path}", data=data, method=method,
            headers={"Content-Type": "application/json"} if data else {},
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read())
            except json.JSONDecodeError:
                raise TintUnavailable(f"HTTP {e.code}: {e.reason}") from e
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            raise TintUnavailable(str(e)) from e
