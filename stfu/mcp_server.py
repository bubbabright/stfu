# stfu/mcp_server.py — MCP server for AI volume control
"""MCP server exposing STFU volume control as tools.

Usage:
    python -m stfu.mcp_server          # stdio transport (runs via __main__)
    stfu-mcp --transport sse           # SSE transport

Tools:
    get_volume       — Read current volume and mute state
    set_volume       — Set volume to 0-100%
    volume_up        — Increase volume by step
    volume_down      — Decrease volume by step
    toggle_mute      — Toggle mute on/off
    set_mute         — Set mute state explicitly
    get_dark_mode    — Read current Windows Dark Mode state (if theme injected)
    toggle_dark_mode — Toggle Windows Dark Mode on/off (if theme injected)
"""
import logging
import threading
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP

log = logging.getLogger("stfu.mcp")


def create_mcp_server(audio, theme=None, *, config):
    """Create and configure FastMCP server with injected controllers.

    Args:
        audio: AudioController instance
        theme: HTTPThemeClient instance, or None to skip registering the
            Dark Mode tools (kept optional for init_mcp()'s legacy 2-arg shim)
        config: AppConfig instance

    Returns:
        Configured FastMCP server instance
    """
    mcp = FastMCP(
        name=config.mcp.name,
        instructions=(
            "Control HTPC volume on pluto. Use get_volume to read state, "
            "set_volume/volume_up/volume_down to change volume, "
            "toggle_mute/set_mute for mute control. "
            "get_dark_mode/toggle_dark_mode control Windows Dark Mode, if available."
        ),
    )

    @mcp.tool()
    def get_volume() -> dict:
        """Get current volume level and mute state.

        Returns:
            dict with keys: volume (int 0-100), muted (bool)
        """
        state = audio.get_state()
        return {"volume": state["volume"], "muted": state["muted"]}

    @mcp.tool()
    def set_volume(percent: int) -> dict:
        """Set HDTV volume to a specific percentage.

        Args:
            percent: Volume level 0-100

        Returns:
            dict with keys: volume (int), muted (bool)
        """
        audio.set_volume(percent)
        state = audio.get_state()
        return {"volume": state["volume"], "muted": state["muted"]}

    @mcp.tool()
    def volume_up() -> dict:
        """Increase volume by configured step amount.

        Returns:
            dict with keys: volume (int), muted (bool)
        """
        audio.volume_up()
        state = audio.get_state()
        return {"volume": state["volume"], "muted": state["muted"]}

    @mcp.tool()
    def volume_down() -> dict:
        """Decrease volume by configured step amount.

        Returns:
            dict with keys: volume (int), muted (bool)
        """
        audio.volume_down()
        state = audio.get_state()
        return {"volume": state["volume"], "muted": state["muted"]}

    @mcp.tool()
    def toggle_mute() -> dict:
        """Toggle mute on/off.

        Returns:
            dict with keys: volume (int), muted (bool)
        """
        audio.toggle_mute()
        state = audio.get_state()
        return {"volume": state["volume"], "muted": state["muted"]}

    @mcp.tool()
    def set_mute(muted: bool) -> dict:
        """Set mute state explicitly.

        Args:
            muted: True to mute, False to unmute

        Returns:
            dict with keys: volume (int), muted (bool)
        """
        audio.set_mute(muted)
        state = audio.get_state()
        return {"volume": state["volume"], "muted": state["muted"]}

    if theme is not None:
        @mcp.tool()
        def get_dark_mode() -> dict:
            """Get current Windows Dark Mode state.

            Returns:
                dict with key: dark_mode (bool)
            """
            return {"dark_mode": theme.get_dark_mode()}

        @mcp.tool()
        def toggle_dark_mode() -> dict:
            """Toggle Windows Dark Mode on/off.

            Returns:
                dict with key: dark_mode (bool)
            """
            return {"dark_mode": theme.toggle_dark_mode()}

    return mcp


def heartbeat_path(config) -> Path:
    """Path to the file start_heartbeat() touches while the MCP process is alive.

    web.py's /mcp/status reads this file's mtime to report liveness.
    """
    return Path(config.log.file).with_name("stfu_mcp.heartbeat")


def start_heartbeat(config) -> None:
    """Touch the heartbeat file on a timer for as long as this process lives.

    A stale file means the process died (crash, kill) — no graceful shutdown
    handling needed, staleness alone is the signal.
    """
    path = heartbeat_path(config)

    def _beat():
        while True:
            path.touch()
            time.sleep(config.mcp.heartbeat_interval)

    threading.Thread(target=_beat, daemon=True).start()