# stfu/audio.py — Windows audio control via pycaw
import logging
import time
from typing import TYPE_CHECKING

import comtypes
from pycaw.pycaw import AudioUtilities

if TYPE_CHECKING:
    from stfu.config import AppConfig

log = logging.getLogger("stfu.audio")


class AudioController:
    """Thread-safe Windows audio volume control."""

    def __init__(self, config: "AppConfig"):
        self.config = config
        self._muted = False
        self._action = ""
        self._action_ts = 0.0

    def _get_interface(self):
        comtypes.CoInitialize()
        device = AudioUtilities.GetSpeakers()
        return device.EndpointVolume

    @property
    def muted(self) -> bool:
        return self._muted

    @property
    def action(self) -> str:
        return self._action

    @property
    def action_ts(self) -> float:
        return self._action_ts

    def get_volume(self) -> int:
        vol = self._get_interface()
        return round(vol.GetMasterVolumeLevelScalar() * 100)

    def set_volume(self, percent: int) -> int:
        percent = max(self.config.volume.min_val,
                      min(self.config.volume.max_val, percent))
        vol = self._get_interface()
        vol.SetMasterVolumeLevelScalar(percent / 100, None)
        self._action = f"{percent}%"
        self._action_ts = time.time()
        log.info("Volume set to %d%%", percent)
        return percent

    def volume_up(self) -> int:
        return self.set_volume(self.get_volume() + self.config.volume.step)

    def volume_down(self) -> int:
        return self.set_volume(self.get_volume() - self.config.volume.step)

    def get_mute(self) -> bool:
        vol = self._get_interface()
        return bool(vol.GetMute())

    def set_mute(self, muted: bool) -> bool:
        vol = self._get_interface()
        vol.SetMute(int(muted), None)
        self._muted = muted
        self._action = "MUTED" if muted else "UNMUTED"
        self._action_ts = time.time()
        log.info("Mute set to %s", muted)
        return muted

    def toggle_mute(self) -> bool:
        new_state = not self.get_mute()
        return self.set_mute(new_state)

    def get_state(self) -> dict:
        return {
            "volume": self.get_volume(),
            "muted": self.get_mute(),
            "action": self._action,
            "action_ts": self._action_ts,
        }
