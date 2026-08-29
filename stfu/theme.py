# stfu/theme.py — Windows Dark Mode control + HTTP client
"""Controls Windows' system Dark Mode (Settings > Personalization > Colors)
via HKCU registry + a WM_SETTINGCHANGE broadcast.

NOT Night Light (the blue-light filter) — that state lives in an
undocumented binary registry blob that's known to break across Windows
updates. Dark Mode is two plain, documented DWORD values instead.

ThemeController talks to HKEY_CURRENT_USER and broadcasts to the caller's
own desktop session, so it only works run from the interactive user's
logon session — see stfu/night_light_helper.py, the only place this class
is ever instantiated. Every other run mode talks to it through
HTTPThemeClient instead of importing ThemeController directly.
"""
import ctypes
import json
import logging
import threading
import urllib.error
import urllib.request
import winreg
from ctypes import wintypes
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from stfu.config import AppConfig

log = logging.getLogger("stfu.theme")

_PERSONALIZE_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
_APPS_VALUE = "AppsUseLightTheme"
_SYSTEM_VALUE = "SystemUsesLightTheme"

_HWND_BROADCAST = 0xFFFF
_WM_SETTINGCHANGE = 0x001A

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.SendNotifyMessageW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPCWSTR,
]
_user32.SendNotifyMessageW.restype = wintypes.BOOL


class ThemeController:
    """Thread-safe Windows Dark Mode control (HKCU registry + live broadcast).

    Only ever constructed inside stfu/night_light_helper.py's interactive
    session — see module docstring.
    """

    def __init__(self, config: "AppConfig"):
        self.config = config
        self._lock = threading.Lock()

    def _read_light_flag(self) -> int:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _PERSONALIZE_KEY, 0, winreg.KEY_READ
        ) as key:
            value, _ = winreg.QueryValueEx(key, _APPS_VALUE)
            return value

    def _write_light_flag(self, value: int) -> None:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, _PERSONALIZE_KEY, 0, winreg.KEY_WRITE
        ) as key:
            winreg.SetValueEx(key, _APPS_VALUE, 0, winreg.REG_DWORD, value)
            winreg.SetValueEx(key, _SYSTEM_VALUE, 0, winreg.REG_DWORD, value)

    def _broadcast_theme_change(self) -> None:
        """Tell running Explorer/apps to repaint now, without a logoff/restart."""
        _user32.SendNotifyMessageW(
            _HWND_BROADCAST, _WM_SETTINGCHANGE, 0, "ImmersiveColorSet",
        )

    def get_dark_mode(self) -> bool:
        """Live-read current Dark Mode state (registry is the source of
        truth, mirroring how AudioController always live-queries pycaw)."""
        with self._lock:
            try:
                return self._read_light_flag() == 0
            except FileNotFoundError:
                log.warning("Personalize key/value missing; assuming light mode")
                return False

    def set_dark_mode(self, enabled: bool) -> bool:
        light_value = 0 if enabled else 1
        with self._lock:
            self._write_light_flag(light_value)
            self._broadcast_theme_change()
        log.info("Dark mode set to %s", enabled)
        return enabled

    def toggle_dark_mode(self) -> bool:
        """Atomic read-modify-write under one lock acquisition, so two
        concurrent toggle requests can't race to a net no-op."""
        with self._lock:
            try:
                current_dark = self._read_light_flag() == 0
            except FileNotFoundError:
                current_dark = False
            new_dark = not current_dark
            self._write_light_flag(0 if new_dark else 1)
            self._broadcast_theme_change()
        log.info("Dark mode toggled to %s", new_dark)
        return new_dark

    def get_state(self) -> dict:
        return {"dark_mode": self.get_dark_mode()}


class ThemeHelperUnavailable(Exception):
    """Raised by HTTPThemeClient when night-light-helper can't be reached."""


class HTTPThemeClient:
    """Relays theme requests to night-light-helper over HTTP.

    Used by every run mode except the helper itself, since HKEY_CURRENT_USER
    and WM_SETTINGCHANGE are scoped to the interactive session the helper
    runs in — a Windows service (LocalSystem, session 0) can't touch either
    directly. See stfu/night_light_helper.py.
    """

    def __init__(self, config: "AppConfig"):
        self._base = f"http://127.0.0.1:{config.theme.helper_port}"
        self._timeout = config.theme.helper_timeout

    def get_dark_mode(self) -> bool:
        return self._request("GET", "/theme")["dark_mode"]

    def toggle_dark_mode(self) -> bool:
        return self._request("POST", "/theme/dark-mode")["dark_mode"]

    def _request(self, method: str, path: str) -> dict:
        req = urllib.request.Request(f"{self._base}{path}", method=method)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            raise ThemeHelperUnavailable(str(e)) from e
