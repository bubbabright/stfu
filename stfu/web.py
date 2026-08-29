# stfu/web.py — Flask web server
import logging
import queue
import urllib.error
import urllib.request
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

from stfu import __version__
from stfu.theme import ThemeHelperUnavailable

log = logging.getLogger("stfu.web")

TEMPLATE_DIR = str(Path(__file__).parent.parent / "templates")


def create_app(audio, theme, config):
    """Create Flask app with injected audio/theme controllers."""
    app = Flask(__name__, template_folder=TEMPLATE_DIR)
    cc_queue: queue.Queue = queue.Queue()

    mqtt_ws_url = f"{config.mqtt.broker}:{config.mqtt.ws_port}"

    @app.route("/")
    def index():
        return render_template(
            "index.html",
            poll_interval=config.web.poll_interval_ms,
            mqtt_ws_url=mqtt_ws_url,
            version=__version__,
            theme_enabled=config.theme.enabled,
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

    @app.route("/theme", methods=["GET"])
    def get_theme():
        if not config.theme.enabled:
            return jsonify({"error": "theme control disabled"}), 404
        try:
            return jsonify({"dark_mode": theme.get_dark_mode()})
        except ThemeHelperUnavailable as e:
            log.warning("Theme helper unreachable: %s", e)
            return jsonify({"error": "theme helper unreachable"}), 503

    @app.route("/theme/dark-mode", methods=["POST"])
    def toggle_dark_mode():
        if not config.theme.enabled:
            return jsonify({"error": "theme control disabled"}), 404
        try:
            return jsonify({"dark_mode": theme.toggle_dark_mode()})
        except ThemeHelperUnavailable as e:
            log.warning("Theme helper unreachable: %s", e)
            return jsonify({"error": "theme helper unreachable"}), 503

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

    @app.route("/cc/stream")
    def cc_stream():
        def event_stream():
            while True:
                try:
                    text = cc_queue.get(timeout=30)
                    yield f"data: {text}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        return Response(event_stream(), mimetype="text/event-stream")

    return app, cc_queue
