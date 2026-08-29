# stfu/night_light_helper.py — interactive-session Dark Mode helper
"""
Runs in the interactive desktop session (via Scheduled Task, started at
logon) because HKEY_CURRENT_USER and WM_SETTINGCHANGE broadcasts are
session-scoped — the main STFU service (LocalSystem, session 0) can't
reach either. Controls Windows *Dark Mode*, not the unrelated "Night
Light" blue-light filter — see CLAUDE.md for why that one was ruled out.

The only process that ever constructs ThemeController directly. Every
other run mode (--service, normal mode, --mcp) talks to this helper
through stfu.theme.HTTPThemeClient over loopback HTTP instead.
"""
import getpass
import logging
import os
import sys
from pathlib import Path

from flask import Flask, jsonify

from stfu.config import acquire_singleton_lock
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

    app = Flask(__name__)

    @app.route("/theme", methods=["GET"])
    def get_theme():
        return jsonify({"dark_mode": theme.get_dark_mode(), "helper_user": getpass.getuser()})

    @app.route("/theme/dark-mode", methods=["POST"])
    def toggle_theme():
        return jsonify({"dark_mode": theme.toggle_dark_mode(), "helper_user": getpass.getuser()})

    log.info("night-light-helper listening on 127.0.0.1:%d", config.theme.helper_port)
    app.run(
        host="127.0.0.1",
        port=config.theme.helper_port,
        debug=False,
        use_reloader=False,
        threaded=True,
    )
