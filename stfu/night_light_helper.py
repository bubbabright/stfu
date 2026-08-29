# stfu/night_light_helper.py — interactive-session Dark Mode + Night Light helper
"""
Runs in the interactive desktop session (via Scheduled Task, started at
logon) because HKEY_CURRENT_USER (Dark Mode's registry values, and the
Win32 API wnl.exe shells out to for Night Light) and WM_SETTINGCHANGE
broadcasts are all session-scoped — the main STFU service (LocalSystem,
session 0) can't reach any of them.

The only process that ever constructs ThemeController or
NightLightController directly. Every other run mode (--service, normal
mode, --mcp) talks to this helper through stfu.theme.HTTPThemeClient /
stfu.nightlight.HTTPNightlightClient over HTTP instead — reachable
across the LAN/Tailscale like every other STFU-facet, not
loopback-restricted.
"""
import getpass
import logging
import os
import sys
from pathlib import Path

from flask import Flask, jsonify, request

from stfu.config import acquire_singleton_lock
from stfu.nightlight import NightLightController, NightLightUnavailable
from stfu.theme import ThemeController

log = logging.getLogger("stfu.night_light_helper")


def run_night_light_helper(config) -> None:
    lock_path = Path(config.log.file).parent / "stfu_night_light_helper.lock"
    try:
        acquire_singleton_lock(lock_path)
    except RuntimeError as e:
        log.error(str(e))
        print(str(e))
        sys.exit(1)

    log.info(
        "night-light-helper starting: user=%s exe=%s cwd=%s",
        getpass.getuser(), sys.executable, os.getcwd(),
    )

    theme = ThemeController(config)

    nightlight = None
    if config.nightlight.enabled:
        nightlight = NightLightController(config.nightlight.wnl_path)

    app = Flask(__name__)

    @app.route("/theme", methods=["GET"])
    @app.route("/theme/dark-mode", methods=["POST"])
    def light_dark_theme():
        if request.method == "POST":
            dark_mode = theme.toggle_dark_mode()
        else:
            dark_mode = theme.get_dark_mode()
        return jsonify({"dark_mode": dark_mode, "helper_user": getpass.getuser()})

    @app.route("/nightlight", methods=["GET", "POST"])
    def nightlight_on_off():
        if nightlight is None:
            return jsonify({"error": "nightlight disabled"}), 404
        try:
            if request.method == "GET":
                return jsonify(nightlight.status())
            data = request.get_json(silent=True) or {}
            state = data.get("state", "toggle")
            if state == "toggle":
                return jsonify(nightlight.toggle())
            elif state in ("on", "off"):
                return jsonify(nightlight.set(state == "on"))
            return jsonify({"error": "state must be on|off|toggle"}), 400
        except NightLightUnavailable as e:
            log.warning("Night light control failed: %s", e)
            return jsonify({"error": str(e)}), 503

    log.info("night-light-helper listening on 0.0.0.0:%d", config.theme.helper_port)
    app.run(
        host="0.0.0.0",
        port=config.theme.helper_port,
        debug=False,
        use_reloader=False,
        threaded=True,
    )
