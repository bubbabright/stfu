# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

STFU — a Windows-only HTPC volume control + closed-caption tool. Runs on a Windows 11 media PC ("pluto"), exposes volume control via a REST web UI, an on-screen overlay, MQTT pub/sub for edge devices (phone/tablet/ESP32), and an MCP server for AI-driven control. No test suite or lint config currently exists in the repo despite references to them in README.md — verify before relying on `pytest`/`ruff`/`black` commands.

## Deployment

Live instance runs on `pluto` (Windows 11 HTPC). Reach it with `ssh pluto`.

## Commands

```bat
setup.bat                        # first-time venv + install
manage.bat                       # interactive menu

python -m stfu                   # web server + overlay
python -m stfu --no-overlay      # web server only
python -m stfu --mcp             # MCP server only (stdio transport, for AI clients)
python -m stfu --service         # run as Windows service (used by NSSM)
python -m stfu --config path.toml  # override config file path
```

The app is Windows-only (pycaw/comtypes for audio, tkinter overlay, optional pywin32 service wrapper) — it will not run on Linux/macOS. There is no test or lint tooling pinned in `requirements.txt`.

## Architecture

Single entry point, four run modes, all sharing the same `AudioController` and `AppConfig`:

- `stfu/__main__.py` — argparse dispatch. Normal mode starts Flask in a daemon thread, then optionally starts the overlay (tkinter) and caption capture in their own daemon threads, then busy-waits (`sleep(1)` loop) until `KeyboardInterrupt`. `--mcp` and `--service` bypass Flask/overlay/captions setup and hand off entirely to `mcp_server.py` / `service.py`.
- `stfu/config.py` — one `@dataclass` per `stfu.toml` section (`VolumeConfig`, `WebConfig`, `OverlayConfig`, `MQTTConfig`, `CCConfig`, `MCPConfig`, `LogConfig`), composed into `AppConfig`. Each dataclass self-validates in `__post_init__` (range/positivity checks) and raises `ValueError` on bad values — config errors are fail-fast at startup, not silently clamped. `load_config()` reads TOML, deep-merges it over the dataclass defaults section-by-section, and warns (not errors) on unknown TOML keys via `VALID_KEYS`. `MQTTConfig.broker` defaults from the `MQTT_BROKER` env var, everything else only from TOML/defaults.
- `stfu/audio.py` — `AudioController` wraps pycaw. COM is initialized and the `EndpointVolume` interface is cached once in `__init__` (not per-call — this was a real perf fix, see README changelog), guarded by a `threading.Lock` since it's shared across the Flask thread, overlay thread, and MCP tool calls.
- `stfu/web.py` — `create_app(audio, config)` factory returns `(Flask app, cc_queue)`. All routes read/mutate state through the injected `AudioController`, no module-level globals. `/cc/stream` (SSE) exists but is currently unused — captions ship over MQTT instead, not this endpoint.
- `stfu/mcp_server.py` — `create_mcp_server(audio, config)` factory using FastMCP, same dependency-injection pattern as `web.py`. Exposes `get_volume`/`set_volume`/`volume_up`/`volume_down`/`toggle_mute`/`set_mute` as MCP tools. `init_mcp()`/`get_mcp()` are a deprecated module-global shim kept only for backward compat — new code should use `create_mcp_server()` directly.
- `stfu/overlay.py` — tkinter on-screen volume display, polls `AudioController` on a timer. Calls `run_overlay()` create a fresh `Tk()` each time — only one overlay can run per process (known limitation, not currently guarded).
- `stfu/captions.py` — `CaptionCapture` grabs screen frames with `mss`, OCRs with Tesseract, publishes to MQTT (`htpc/captions`). Key design point: it checks MQTT subscriber presence before running Tesseract, so OCR only burns CPU when something is actually listening for captions. Reconnects to the broker with exponential backoff (1s→30s, jittered) and has a `_stop_event`/`stop()` for clean shutdown.
- `stfu/service.py` — NSSM/pywin32 Windows service wrapper. Imports `win32serviceutil` etc. in a `try/except ImportError` so the module still runs directly (calls `_service_main()`) on a machine without pywin32. `_service_main()` re-implements the same thread-startup sequence as `__main__.py`'s normal mode (Flask + overlay + captions), so changes to that startup sequence generally need to be made in both places.

State flows one way through MQTT: `pycaw` (this app) is the source of truth for volume, publishing to `htpc/volume/state`; edge devices (browsers via MQTT-over-WebSocket, ESP32 nodes) publish commands to `htpc/volume/set` which this app subscribes to. Caption text flows `mss`/Tesseract → `htpc/captions` → tkinter overlay + browsers.

`archive/` is legacy pre-rewrite code (gitignored) — not part of the active package, don't treat it as current architecture reference.
