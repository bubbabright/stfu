# stfu/web.py — Flask web server
import logging
import queue
import time
import urllib.error
import urllib.request
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

from stfu import __version__
from stfu.captions import CCUnavailable
from stfu.nightlight import NightlightHelperUnavailable
from stfu.tint import TintUnavailable

log = logging.getLogger("stfu.web")

TEMPLATE_DIR = str(Path(__file__).parent.parent / "templates")


def create_app(audio, config, nightlight=None, tint=None, cc=None):
    """Create Flask app with injected audio/nightlight/tint/cc controllers."""
    app = Flask(__name__, template_folder=TEMPLATE_DIR)

    mqtt_ws_url = f"{config.mqtt.broker}:{config.mqtt.ws_port}"

    @app.route("/")
    def index():
        return render_template(
            "index.html",
            poll_interval=config.web.poll_interval_ms,
            mqtt_ws_url=mqtt_ws_url,
            version=__version__,
            nightlight_enabled=config.nightlight.enabled,
            tint_enabled=config.tint.enabled,
            cc_enabled=config.cc.enabled,
            mcp_enabled=config.mcp.enabled,
        )

    @app.route("/volume", methods=["GET"])
    def get_volume():
        state = audio.get_state()
        return jsonify({"volume": state["volume"], "muted": state["muted"]})

    @app.route("/volume/up", methods=["POST"])
    def volume_up():
        audio.volume_up()
        state = audio.get_state()
        return jsonify({"volume": state["volume"], "muted": state["muted"]})

    @app.route("/volume/down", methods=["POST"])
    def volume_down():
        audio.volume_down()
        state = audio.get_state()
        return jsonify({"volume": state["volume"], "muted": state["muted"]})

    @app.route("/volume/set", methods=["POST"])
    def set_volume():
        data = request.get_json() or {}
        try:
            percent = int(data.get("volume"))
            audio.set_volume(percent)
        except (ValueError, TypeError):
            pass
        state = audio.get_state()
        return jsonify({"volume": state["volume"], "muted": state["muted"]})

    @app.route("/volume/mute", methods=["POST"])
    def toggle_mute():
        audio.toggle_mute()
        state = audio.get_state()
        return jsonify({"volume": state["volume"], "muted": state["muted"]})

    @app.route("/overlay/status", methods=["GET"])
    def overlay_status():
        url = f"http://127.0.0.1:{config.overlay.status_port}/status"
        try:
            with urllib.request.urlopen(url, timeout=config.overlay.status_timeout):
                return jsonify({"active": True})
        except (urllib.error.URLError, OSError, TimeoutError):
            return jsonify({"active": False})

    @app.route("/nightlight", methods=["GET", "POST"])
    def nightlight_on_off():
        if not config.nightlight.enabled or nightlight is None:
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
        except NightlightHelperUnavailable as e:
            log.warning("Night light helper unreachable: %s", e)
            return jsonify({"error": "nightlight helper unreachable"}), 503

    @app.route("/tint", methods=["GET"])
    def tint_status():
        if not config.tint.enabled or tint is None:
            return jsonify({"error": "tint disabled"}), 404
        try:
            return jsonify(tint.status())
        except TintUnavailable as e:
            log.warning("Tint helper unreachable: %s", e)
            return jsonify({"error": "tint helper unreachable"}), 503

    @app.route("/tint/opacity", methods=["POST"])
    def tint_opacity():
        if not config.tint.enabled or tint is None:
            return jsonify({"error": "tint disabled"}), 404
        data = request.get_json(silent=True) or {}
        try:
            alpha = float(data.get("alpha"))
        except (TypeError, ValueError):
            return jsonify({"error": "alpha must be a number"}), 400
        try:
            return jsonify(tint.set_opacity(alpha))
        except TintUnavailable as e:
            log.warning("Tint helper unreachable: %s", e)
            return jsonify({"error": "tint helper unreachable"}), 503

    @app.route("/mcp/status", methods=["GET"])
    def mcp_status():
        if not config.mcp.enabled:
            return jsonify({"error": "mcp disabled"}), 404
        from stfu.mcp_server import heartbeat_path  # lazy: only needed if mcp is enabled

        try:
            age = time.time() - heartbeat_path(config).stat().st_mtime
            active = age <= config.mcp.heartbeat_stale_after
        except OSError:
            active = False
        return jsonify({"active": active})

    @app.route("/config", methods=["GET"])
    def get_config():
        return jsonify({
            "volume_step": config.volume.step,
            "poll_interval_ms": config.web.poll_interval_ms,
        })

    @app.route("/config", methods=["POST"])
    def update_config():
        data = request.get_json() or {}
        if "volume_step" in data:
            try:
                step = int(data["volume_step"])
                if 1 <= step <= 100:
                    config.volume.step = step
            except ValueError:
                pass
        if "poll_interval_ms" in data:
            try:
                interval = int(data["poll_interval_ms"])
                if interval >= 100:
                    config.web.poll_interval_ms = interval
            except ValueError:
                pass
        return jsonify({
            "volume_step": config.volume.step,
            "poll_interval_ms": config.web.poll_interval_ms,
        })

    @app.route("/cc", methods=["GET"])
    def cc_status():
        if not config.cc.enabled or cc is None:
            return jsonify({"error": "cc disabled"}), 404
        try:
            return jsonify(cc.status())
        except CCUnavailable as e:
            log.warning("CC process unreachable: %s", e)
            return jsonify({"error": "cc process unreachable"}), 503

    return app
