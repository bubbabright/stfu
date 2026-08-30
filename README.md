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
manage.bat  # option 7 = stop all, then 1/2/3/4 to start what you need back
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

## Changelog

### v4.1.0 (2025-07-16)
**Stability & Version Display**
- Version badge add to web UI (render from `stfu/__init__.py`)
- **Audio**: pycaw COM interface cache in `AudioController.__init__` with `threading.Lock` (fix CoInitialize call every time)
- **Captions**: MQTT reconnect add, exponential backoff (1s→30s, 10% jitter) + `stop()` method for clean shutdown
- **Config**: Full validate via `__post_init__` on all dataclasses; unknown TOML keys now warn; `MQTT_BROKER` env var override
- **Overlay**: Fix bare `except:` → now log error with traceback
- **MCP**: Global state gone; new `create_mcp_server(audio, config)` factory, closure injection
- **Defaults**: `volume.default = 20` sync in config.py and stfu.toml

### v4.0.0
First release — web UI, overlay, MQTT captions, MCP server, Windows service support.

## Commands

| Command | Description |
|---------|-------------|
| `python -m stfu` | Run web server + overlay |
| `python -m stfu --no-overlay` | Run without overlay |
| `python -m stfu --mcp` | Run MCP server (for AI control) |
| `python -m stfu --service` | Run as Windows service |
| `manage.bat` | Interactive menu |

## Architecture

```
[pluto - Windows 11 HTPC]
  ├── audio.py (pycaw)          → REST API + MQTT state
  ├── web.py (Flask :5000)      → browser UI
  ├── overlay.py (tkinter)      → on-screen volume display
  ├── captions.py (mss+OCR)     → MQTT htpc/captions
  └── mcp_server.py (FastMCP)   → AI volume control

        ↕ MQTT (192.168.1.215:1883)

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
| `/config` | GET/POST | Read/update config |

## MCP Server

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

## Windows Service (NSSM)

```bat
# Install
nssm install STFU python -m stfu --service
nssm set STFU AppDirectory C:\scripts\stfu
nssm set STFU DisplayName "STFU Volume Control"
nssm set STFU Start SERVICE_AUTO_START
nssm set STFU AppStdout C:\scripts\stfu\logs\service-stdout.log
nssm set STFU AppStderr C:\scripts\stfu\logs\service-stderr.log

# Control
nssm start STFU
nssm stop STFU
nssm remove STFU confirm
```

## Configuration

Edit `stfu.toml` to customize. All values got sane defaults.

### Key Sections

- `[volume]` — step size, min/max, default
- `[web]` — host, port, poll interval
- `[overlay]` — position, fonts, opacity, duration
- `[mqtt]` — broker, port, topics
- `[cc]` — OCR region, thresholds, scan interval
- `[mcp]` — server name, transport
- `[log]` — level, rotation, retention

## MQTT Topics

| Topic | Direction | Purpose |
|-------|-----------|---------|
| `htpc/captions` | HTPC → edges | OCR captions |
| `htpc/volume/state` | HTPC → edges | Volume state broadcast |
| `htpc/volume/set` | edges → HTPC | Volume commands |

## Requirements

- Windows 11 (pluto)
- Python 3.11+
- NSSM (for service mode)
- Tesseract OCR (for captions, optional)
- Mosquitto broker (for MQTT, optional)

## Changelog

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

```bash
# Install dev dependencies
pip install -e .[dev]

# Run tests
python -m pytest tests/

# Lint
ruff check stfu/
black stfu/
```

## Known Issues

- **Overlay single Tk instance** — `run_overlay()` make new `Tk()` each call; only one overlay run per process. Guard or reuse root.
- **Busy-wait loops** — `__main__.py:124` and `service.py:74` use `sleep(1)` poll. Use `threading.Event` for clean shutdown instead.
- **SSE endpoint unused** — `web.py:/cc/stream` exist but captions use MQTT. Remove or wire up.
- **Per-app volume** — pycaw session API not yet expose via REST/MCP.

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
3. Change with tests
4. Run `ruff check` and `black --check`
5. Submit PR

## License

MIT — do what you want.