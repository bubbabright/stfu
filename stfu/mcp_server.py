# stfu/mcp_server.py — MCP server for AI volume control
"""MCP server exposing STFU volume control as tools.

Usage:
    python -m stfu.mcp_server          # stdio transport (runs via __main__)
    stfu-mcp --transport sse           # SSE transport

Tools:
    get_volume     — Read current volume and mute state
    set_volume     — Set volume to 0-100%
    volume_up      — Increase volume by step
    volume_down    — Decrease volume by step
    toggle_mute    — Toggle mute on/off
    set_mute       — Set mute state explicitly
"""
import logging

from mcp.server.fastmcp import FastMCP

log = logging.getLogger("stfu.mcp")


def create_mcp_server(audio, config):
    """Create and configure FastMCP server with injected audio controller.

    Args:
        audio: AudioController instance
        config: AppConfig instance

    Returns:
        Configured FastMCP server instance
    """
    mcp = FastMCP(
        name=config.mcp.name,
        instructions=(
            "Control HTPC volume on pluto. Use get_volume to read state, "
            "set_volume/volume_up/volume_down to change volume, "
            "toggle_mute/set_mute for mute control."
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

    return mcp


# Backward compatibility: legacy init_mcp() for existing callers
# This creates a module-level server that can be run directly
_audio = None
_config = None
_mcp = None


def init_mcp(audio, config):
    """Legacy function - use create_mcp_server instead.

    Creates a module-level MCP server for backward compatibility
    with `python -m stfu.mcp_server` entry point.
    """
    global _audio, _config, _mcp
    _audio = audio
    _config = config
    _mcp = create_mcp_server(audio, config)
    log.warning("init_mcp() is deprecated; use create_mcp_server()")


def get_mcp():
    """Get the module-level MCP server (created by init_mcp)."""
    if _mcp is None:
        raise RuntimeError("MCP server not initialized - call init_mcp() first")
    return _mcp