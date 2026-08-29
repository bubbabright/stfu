# stfu/nightlight.py — Windows Night Light via wnl CLI + HTTP client
"""wnl shells out to a Win32 API that reads/writes the interactive user's
HKEY_CURRENT_USER — session-scoped, same constraint as stfu/theme.py's
Dark Mode control. NightLightController must only run inside
night_light_helper.py's interactive session; every other run mode talks
to it through HTTPNightlightClient over that same helper's HTTP port.
"""
import json
import logging
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from stfu.config import AppConfig

log = logging.getLogger("stfu.nightlight")


class NightLightUnavailable(Exception):
    """wnl missing or failed."""


class NightLightController:
    def __init__(self, wnl_path: str):
        self.wnl = Path(wnl_path)

    def _run(self, *args: str) -> str:
        if not self.wnl.exists():
            raise NightLightUnavailable(f"wnl not found: {self.wnl}")
        try:
            result = subprocess.run(
                [str(self.wnl), *args],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            raise NightLightUnavailable(str(e)) from e
        if result.returncode != 0:
            msg = (result.stderr or result.stdout or "wnl failed").strip()
            raise NightLightUnavailable(msg)
        return result.stdout.strip()

    def status(self) -> dict:
        out = self._run("status")
        enabled = False
        for line in out.splitlines():
            if "is enabled:" in line.lower():
                enabled = "true" in line.lower()
                break
        return {"enabled": enabled, "raw": out}

    def set(self, on: bool) -> dict:
        self._run("on" if on else "off")
        return self.status()

    def toggle(self) -> dict:
        return self.set(not self.status()["enabled"])


class NightlightHelperUnavailable(Exception):
    """Raised by HTTPNightlightClient when night-light-helper can't be reached."""


class HTTPNightlightClient:
    """Relays night light requests to night-light-helper over HTTP.

    Used by every run mode except the helper itself — see module
    docstring. Reuses the theme helper's port/timeout config since it's
    the same interactive-session process.
    """

    def __init__(self, config: "AppConfig"):
        self._base = f"http://127.0.0.1:{config.theme.helper_port}"
        self._timeout = config.theme.helper_timeout

    def status(self) -> dict:
        return self._request("GET", "/nightlight")

    def set(self, on: bool) -> dict:
        return self._request("POST", "/nightlight", {"state": "on" if on else "off"})

    def toggle(self) -> dict:
        return self._request("POST", "/nightlight", {"state": "toggle"})

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            f"{self._base}{path}", data=data, method=method,
            headers={"Content-Type": "application/json"} if data else {},
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            raise NightlightHelperUnavailable(str(e)) from e
