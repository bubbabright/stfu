# stfu/night_light_helper.py — interactive-session Night Light helper
"""
Runs in the interactive desktop session (started by hand via manage.bat)
because the Win32 API wnl.exe shells out to for Night Light touches
HKEY_CURRENT_USER, which is session-scoped — the main STFU process
(if ever run headless) can't reach it.

The only process that ever constructs NightLightController directly.
Every other run mode (normal mode, --mcp) talks to this helper through
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

    nightlight = None
    if config.nightlight.enabled:
        nightlight = NightLightController(config.nightlight.wnl_path)

    app = Flask(__name__)

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

    log.info("night-light-helper listening on 0.0.0.0:%d", config.nightlight.helper_port)
    app.run(
        host="0.0.0.0",
        port=config.nightlight.helper_port,
        debug=False,
        use_reloader=False,
        threaded=True,
    )
