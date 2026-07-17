# stfu/mcp_server.py — MCP server for AI volume control
"""MCP server exposing STFU volume control as tools.

Usage:
    python -m stfu.mcp_server          # stdio transport
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

# Global audio controller reference (set by main)
_audio = None
_config = None


def init_mcp(audio, config):
    """Initialize MCP server with audio controller."""
    global _audio, _config
    _audio = audio
    _config = config


mcp = FastMCP(
    name=config.mcp.name if _config else "stfu",
    instructions="Control HTPC volume on pluto. Use get_volume to read state, set_volume/volume_up/volume_down to change volume, toggle_mute/set_mute for mute control.",
)


@mcp.tool()
def get_volume() -> dict:
    """Get current volume level and mute state.

    Returns:
        dict with keys: volume (int 0-100), muted (bool)
    """
    state = _audio.get_state()
    return {"volume": state["volume"], "muted": state["muted"]}


@mcp.tool()
def set_volume(percent: int) -> dict:
    """Set HDTV volume to a specific percentage.

    Args:
        percent: Volume level 0-100

    Returns:
        dict with keys: volume (int), muted (bool)
    """
    _audio.set_volume(percent)
    state = _audio.get_state()
    return {"volume": state["volume"], "muted": state["muted"]}


@mcp.tool()
def volume_up() -> dict:
    """Increase volume by configured step amount.

    Returns:
        dict with keys: volume (int), muted (bool)
    """
    _audio.volume_up()
    state = _audio.get_state()
    return {"volume": state["volume"], "muted": state["muted"]}


@mcp.tool()
def volume_down() -> dict:
    """Decrease volume by configured step amount.

    Returns:
        dict with keys: volume (int), muted (bool)
    """
    _audio.volume_down()
    state = _audio.get_state()
    return {"volume": state["volume"], "muted": state["muted"]}


@mcp.tool()
def toggle_mute() -> dict:
    """Toggle mute on/off.

    Returns:
        dict with keys: volume (int), muted (bool)
    """
    _audio.toggle_mute()
    state = _audio.get_state()
    return {"volume": state["volume"], "muted": state["muted"]}


@mcp.tool()
def set_mute(muted: bool) -> dict:
    """Set mute state explicitly.

    Args:
        muted: True to mute, False to unmute

    Returns:
        dict with keys: volume (int), muted (bool)
    """
    _audio.set_mute(muted)
    state = _audio.get_state()
    return {"volume": state["volume"], "muted": state["muted"]}
