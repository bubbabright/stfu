# stfu/captions.py — OCR-based closed caption capture via MQTT
import logging
import time

import numpy as np
import paho.mqtt.client as mqtt
import pytesseract
from PIL import Image

log = logging.getLogger("stfu.captions")


class CaptionCapture:
    """Screen-grab OCR loop publishing captions over MQTT."""

    def __init__(self, config):
        self.config = config
        self.cc = config.cc
        self.client = None
        self._last_text = ""
        self._last_white_count = 0

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

        self.client = mqtt.Client()
        self.client.connect(self.config.mqtt.broker, self.config.mqtt.port)
        self.client.loop_start()
        log.info("MQTT connected to %s:%d", self.config.mqtt.broker, self.config.mqtt.port)

        self._run_loop(mss)

    def _run_loop(self, mss_module):
        region_cfg = self.cc.capture_region
        threshold = self.cc.pixel_threshold

        while True:
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
                log.error("Caption capture error: %s", e)

            time.sleep(self.cc.scan_interval)

    @staticmethod
    def _count_white(arr, threshold):
        mask = (
            (arr[:, :, 0] > threshold)
            & (arr[:, :, 1] > threshold)
            & (arr[:, :, 2] > threshold)
        )
        return int(np.sum(mask))
