# stfu/captions.py — OCR-based closed caption capture via MQTT
import json
import logging
import random
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import paho.mqtt.client as mqtt
import pytesseract
from PIL import Image
from flask import Flask

from stfu.config import acquire_singleton_lock

log = logging.getLogger("stfu.captions")

# Reconnection parameters
RECONNECT_BASE_DELAY = 1.0  # seconds
RECONNECT_MAX_DELAY = 30.0  # seconds
RECONNECT_JITTER = 0.1      # 10% jitter


class CaptionCapture:
    """Screen-grab OCR loop publishing captions over MQTT."""

    def __init__(self, config):
        self.config = config
        self.cc = config.cc
        self.client = None
        self._last_text = ""
        self._last_white_count = 0
        self._stop_event = threading.Event()
        self._reconnect_lock = threading.Lock()
        self._reconnecting = False

    def start(self):
        if not self.cc.enabled:
            log.info("Captions disabled in config")
            return

        try:
            import mss
        except ImportError:
            log.error("mss not installed — captions unavailable")
            return

        pytesseract.pytesseract.tesseract_cmd = self.cc.tesseract_cmd

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        self._connect_with_retry()
        self.client.loop_start()
        log.info("MQTT connecting to %s:%d", self.config.mqtt.broker, self.config.mqtt.port)

        self._run_loop(mss)

    def stop(self):
        """Gracefully stop the capture loop and MQTT client."""
        self._stop_event.set()
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()

    def _connect_with_retry(self):
        """Connect with exponential backoff retry."""
        delay = RECONNECT_BASE_DELAY
        while not self._stop_event.is_set():
            try:
                self.client.connect(self.config.mqtt.broker, self.config.mqtt.port)
                return
            except Exception as e:
                log.warning("MQTT connect failed: %s — retrying in %.1fs", e, delay)
                if self._stop_event.wait(delay):
                    return
                delay = min(delay * 2, RECONNECT_MAX_DELAY) * (1 + random.uniform(-RECONNECT_JITTER, RECONNECT_JITTER))

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            log.info("MQTT connected to %s:%d", self.config.mqtt.broker, self.config.mqtt.port)
            client.subscribe(self.config.mqtt.topic_volume_set)
            log.debug("Subscribed to %s", self.config.mqtt.topic_volume_set)
        else:
            log.error("MQTT connect failed: reason_code=%d", reason_code)

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        if reason_code != 0:
            log.warning("MQTT disconnected unexpectedly: reason_code=%d", reason_code)
            if not self._stop_event.is_set() and not self._reconnecting:
                self._schedule_reconnect()
        else:
            log.info("MQTT disconnected cleanly")

    def _schedule_reconnect(self):
        """Schedule reconnection in a separate thread to avoid blocking loop."""
        with self._reconnect_lock:
            if self._reconnecting:
                return
            self._reconnecting = True

        def _reconnect():
            try:
                self._connect_with_retry()
                self.client.reconnect()
            finally:
                with self._reconnect_lock:
                    self._reconnecting = False

        threading.Thread(target=_reconnect, daemon=True).start()

    def _on_message(self, client, userdata, msg):
        # Handle incoming volume commands if needed
        pass

    def _run_loop(self, mss_module):
        region_cfg = self.cc.capture_region
        threshold = self.cc.pixel_threshold

        while not self._stop_event.is_set():
            try:
                with mss_module.mss() as sct:
                    region = {
                        "top": region_cfg["top_offset"] + (region_cfg["height"] // region_cfg["height_divisor"]),
                        "left": 0,
                        "width": region_cfg["width"],
                        "height": region_cfg["height"] // region_cfg["height_divisor"],
                    }
                    img = sct.grab(region)
                    img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")

                arr = np.array(img)
                white_count = self._count_white(arr, threshold)
                delta = abs(white_count - self._last_white_count)

                if delta > self.cc.white_threshold:
                    result = np.zeros_like(arr)
                    mask = (
                        (arr[:, :, 0] > threshold)
                        & (arr[:, :, 1] > threshold)
                        & (arr[:, :, 2] > threshold)
                    )
                    result[mask] = [255, 255, 255]
                    filtered = Image.fromarray(result)
                    text = pytesseract.image_to_string(filtered).strip()

                    if text and text != self._last_text:
                        self.client.publish(self.config.mqtt.topic_captions, text)
                        self._last_text = text
                        log.debug("Caption: %s", text[:80])

                self._last_white_count = white_count
            except Exception as e:
                log.error("Caption capture error: %s", e, exc_info=True)

            self._stop_event.wait(self.cc.scan_interval)

    @staticmethod
    def _count_white(arr, threshold):
        mask = (
            (arr[:, :, 0] > threshold)
            & (arr[:, :, 1] > threshold)
            & (arr[:, :, 2] > threshold)
        )
        return int(np.sum(mask))


def run_cc(config) -> None:
    lock_path = Path(config.log.file).parent / "stfu_cc.lock"
    try:
        acquire_singleton_lock(lock_path)
    except RuntimeError as e:
        log.error(str(e))
        print(str(e))
        sys.exit(1)

    cc = CaptionCapture(config)

    def _run_control_server():
        app = Flask(__name__)

        @app.route("/status", methods=["GET"])
        def status():
            return jsonify({"active": True})

        log.info("cc control server listening on 0.0.0.0:%d", config.cc.control_port)
        app.run(
            host="0.0.0.0",
            port=config.cc.control_port,
            debug=False,
            use_reloader=False,
            threaded=True,
        )

    threading.Thread(target=_run_control_server, daemon=True).start()

    if config.cc.enabled:
        cc_thread = threading.Thread(target=cc.start, daemon=True)
        cc_thread.start()
        log.info("Caption capture started")
    else:
        log.info("Captions disabled in config")

    log.info("CC mode running")
    while True:
        time.sleep(1)


class CCUnavailable(Exception):
    """Raised by HTTPCCClient when the cc process can't be reached."""


class HTTPCCClient:
    """Relays cc status requests to the --cc-only process over HTTP."""

    def __init__(self, config):
        self._base = f"http://127.0.0.1:{config.cc.control_port}"
        self._timeout = config.cc.control_timeout

    def status(self) -> dict:
        return self._request("GET", "/status")

    def _request(self, method: str, path: str) -> dict:
        req = urllib.request.Request(
            f"{self._base}{path}", method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read())
            except json.JSONDecodeError:
                raise CCUnavailable(f"HTTP {e.code}: {e.reason}") from e
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            raise CCUnavailable(str(e)) from e