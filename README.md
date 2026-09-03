# stfu — HTPC Volume Control

> Volume control + closed caption for HTPC. No app install need. Any LAN browser work.

## Quick Start

```bat
# First time setup
setup.bat

# Or manually
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m stfu
```

Open `http://pluto:5000` from any device on LAN.

## Updating / Deploying to pluto

Dev checkout and pluto's `C:\scripts\stfu` are **separate git clones** of
this repo, not shared storage — a local edit isn't live until pushed and
pulled.

```bash
# 1. On the dev machine: commit + push
git push origin master

# 2. On pluto: pull
ssh pluto
cd C:\scripts\stfu
git status              # check for local uncommitted edits first
git pull origin master  # stash first if the working tree is dirty

# 3. Restart the affected module(s) — no autostart, manage.bat runs them by hand
manage.bat  # option 8 = stop all, then 1 (all) or 2-5 (one module) to start back up
```

No Scheduled Tasks anymore (dropped 2026-08-30 — pluto runs for weeks
between reboots, autostart wasn't worth the trouble it caused: one night
every module turned up double-running, cause never conclusively pinned
down). If you still see a stale process after stopping, find and kill it
directly:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Select ProcessId,CommandLine | findstr stfu
```

An old PID still listed after a stop will make the new instance's
singleton lock (`stfu.lock`) refuse to start — `taskkill /PID <id> /T /F`
it first.

## Commands

| Command | Description |
|---------|-------------|
| `python -m stfu` | Run web server + overlay + captions in one process (dev/manual use) |
| `python -m stfu --no-overlay` | Run web server only — the "web" module |
| `python -m stfu --overlay-only` | Run standalone volume overlay only — the "overlay" module |
| `python -m stfu --night-light-helper` | Run Night Light helper — the "nightlight" module, interactive session only |
| `python -m stfu --tint-only` | Run standalone black tint overlay only — the "tint" module, interactive session only |
| `python -m stfu --mcp` | Run MCP server (stdio, for AI control) |
| `python -m stfu --config path.toml` | Override the config file path |
| `manage.bat` | Interactive menu to start/stop/status each module |

There is no `--service`/NSSM mode — no `service.py` exists in this repo.
Everything runs manually via `manage.bat`, no autostart (see Updating /
Deploying above).

## Architecture

```
[pluto - Windows 11 HTPC]
  ├── audio.py (pycaw)                    → volume state, shared by everything below
  ├── web.py (Flask :5000)                → browser UI + REST API
  ├── overlay.py (tkinter)                → on-screen volume/mute display, --overlay-only
  ├── night_light_helper.py (Flask :5100) → Night Light control, interactive session, --night-light-helper
  ├── tint.py (tkinter + Flask :5103)     → black sleep-tint veil, interactive session, --tint-only
  ├── captions.py (mss+OCR)               → MQTT htpc/captions
  └── mcp_server.py (FastMCP)             → AI volume control, --mcp (off by default)

        ↕ MQTT (broker set in stfu.toml)

[Edge devices — any LAN browser]
  ├── phone / tablet
  ├── ESP32 voice devices
  └── any browser
```

## REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI |
| `/volume` | GET | Get volume + mute state |
| `/volume/up` | POST | Volume up by step |
| `/volume/down` | POST | Volume down by step |
| `/volume/set` | POST | Set volume (`{"volume": 75}`) |
| `/volume/mute` | POST | Toggle mute |
| `/overlay/status` | GET | Volume overlay liveness (for the web UI's status dot) |
| `/nightlight` | GET/POST | Night Light status / set (`{"state": "on"\|"off"\|"toggle"}`) — 404 if disabled |
| `/tint` | GET | Tint overlay status (`{"active", "alpha"}`) — 404 if disabled |
| `/tint/opacity` | POST | Set tint darkness (`{"alpha": 0.0-1.0}`) — 404 if disabled |
| `/mcp/status` | GET | MCP liveness via heartbeat file (for the web UI's status dot) — 404 unless `mcp.enabled` |
| `/config` | GET/POST | Read/update runtime config (volume step, poll interval) |

## MCP Server

**Off by default** — `mcp.enabled = false` in `stfu.toml`. Flip it on to use these.

MCP server expose these tools for AI control:

- `get_volume` — read current volume/mute state
- `set_volume(percent)` — set volume 0-100
- `volume_up()` — bump up by step
- `volume_down()` — bump down by step
- `toggle_mute()` — toggle mute
- `set_mute(muted)` — set mute direct

Configure in your MCP client:

```json
{
  "mcpServers": {
    "stfu": {
      "command": "python",
      "args": ["-m", "stfu", "--mcp"],
      "cwd": "C:\\scripts\\stfu"
    }
  }
}
```

## Configuration

Edit `stfu.toml` to customize. All values got sane defaults.

### Key Sections

- `[volume]` — step size, min/max, default
- `[web]` — host, port, poll interval
- `[overlay]` — position, fonts, opacity, duration
- `[mqtt]` — broker, port, topics
- `[cc]` — OCR region, thresholds, scan interval
- `[nightlight]` — enabled, `wnl` CLI path, helper listen port/timeout
- `[tint]` — enabled, max opacity clamp, control-server port/timeout
- `[mcp]` — enabled (off by default), server name, transport, heartbeat timing
- `[log]` — level, rotation, retention

## MQTT Topics

| Topic | Direction | Purpose |
|-------|-----------|---------|
| `htpc/captions` | HTPC → edges | OCR captions |
| `htpc/volume/state` | HTPC → edges | Volume state broadcast — **defined in config, nothing publishes to it yet** |
| `htpc/volume/set` | edges → HTPC | Volume commands — `captions.py` subscribes, but the handler is currently a no-op stub (`_on_message` does nothing); this is the REST→MQTT migration's landing spot, still in progress |

## Requirements

- Windows 11 (pluto)
- Python 3.11+
- `wnl` CLI (for Night Light control, optional — path set in `[nightlight] wnl_path`)
- Tesseract OCR (for captions, optional)
- Mosquitto broker (for MQTT, optional)

## Changelog

### v4.4.1 (2026-09-03)
**Dark Mode removed, MCP fixed, black tint overlay added**

- **Removed**: `stfu/theme.py` (Windows Dark Mode control) gone entirely — module, `/theme`+`/theme/dark-mode` routes, MCP `get_dark_mode`/`toggle_dark_mode` tools, web UI button. `NightLightConfig` now owns the helper port/timeout `ThemeConfig` used to hold (still port `5100`, same helper process).
- **Fixed**: `python -m stfu --mcp` was crashing on every invocation (`__main__.py` discarded `create_mcp_server()`'s return value and read a never-populated module global instead). MCP now defaults **off** (`mcp.enabled = false`) — fixed but parked until re-enabled.
- **Added**: web UI status light for MCP, backed by a heartbeat file (`stfu.mcp_server.heartbeat_path`/`start_heartbeat`) since MCP runs over stdio with no port to poll.
- **Added**: `stfu/tint.py` — a new `--tint-only` module, a fullscreen click-through black veil ("night light on steroids") controlled by a slider in the web UI (`/tint`, `/tint/opacity`). Own process, own transparency technique (`WS_EX_LAYERED|WS_EX_TRANSPARENT` + `-alpha`, not `overlay.py`'s colorkey trick — black is already that trick's transparent-color key).
- **Fixed**: tint slider polled at the 10s status-dot cadence instead of volume's ~1s cadence — multiple open web UI tabs could see up to 10s of lag after a slider move on another device.
- Docs: corrected several stale claims in this file (see git history) — `--service`/NSSM mode never existed in this repo, `pytest`/`ruff`/`black` aren't configured here, duplicate Changelog section merged into one.

### v4.1.0 (2026-07-16)
**Stability & Config Fixes**

- **Audio**: pycaw COM interface cache in `AudioController.__init__` + `threading.Lock` add for thread safety (was recreate every call)
- **MQTT**: Exponential backoff reconnect add (1s→30s) in `CaptionCapture` with `_stop_event` for clean shutdown
- **Config**: Full validate via `__post_init__` on all dataclasses; unknown TOML keys now warn; `MQTT_BROKER` env var override
- **Config**: Volume default mismatch fix (now `20` both `stfu.toml` and `config.py`)
- **MCP**: Global state gone; new `create_mcp_server(audio, config)` factory, dependency injection
- **Overlay**: Fix bare `except: pass` → now log errors with traceback
- **Web UI**: Version badge shown (`v{{ version }}`)

### v4.0.0
- First release: web UI, overlay, MQTT captions, MCP server, Windows service

## Development

No test suite or lint config is pinned in this repo — no `tests/`, no
`pytest.ini`/`pyproject.toml`, no `ruff`/`black` in `requirements.txt`.
Verify changes by running the affected module directly
(`python -m stfu --no-overlay`, etc.) and exercising it.

## Known Issues

- **Overlay single Tk instance** — `run_overlay()` make new `Tk()` each call; only one overlay run per process. Guard or reuse root.
- **Busy-wait loop** — `__main__.py`'s normal-mode `while True: time.sleep(1)` (currently around line 190). Use `threading.Event` for clean shutdown instead.
- **SSE endpoint unused** — `web.py:/cc/stream` exist but captions use MQTT. Remove or wire up.
- **Per-app volume** — pycaw session API not yet expose via REST/MCP.
- **Tint overlay: primary display only** — no multi-monitor support yet (same limitation as the volume overlay).

## Roadmap

### v1.2 — Observability
- [ ] Structured logging (JSON) for Loki/Grafana
- [ ] `/health` endpoint for monitoring
- [ ] Prometheus metrics (`/metrics`)
- [ ] Request ID correlation across REST + MQTT

### v1.3 — Features
- [ ] WebSocket for real-time volume state (replace polling)
- [ ] Multiple audio endpoint support (select output device)
- [ ] Per-app volume control via pycaw session API
- [ ] Caption history in web UI (searchable)
- [ ] MQTT TLS + auth support
- [ ] Home Assistant discovery integration

### v1.4 — AI/Automation
- [ ] MCP server: add `list_devices` tool
- [ ] MCP server: add `set_device` tool
- [ ] Voice command intent mapping (eg "make it louder" → volume_up)
- [ ] Scheduled volume profiles (night mode, movie mode)
- [ ] LLM-driven caption summarization via MCP

### v2.0 — Cross-platform
- [ ] Linux support (PulseAudio/PipeWire via `pactl` or `wpctl`)
- [ ] macOS support (CoreAudio via `osascript` or `SwitchAudioSource`)
- [ ] Docker image for headless deployment
- [ ] ARM64 builds for Pi/ESP32 edge nodes

## Contributing

1. Fork repo
2. Make feature branch
3. Verify by running the affected module and exercising it (no test/lint tooling exists here yet — see Development)
4. Submit PR

## License

MIT — do what you want.