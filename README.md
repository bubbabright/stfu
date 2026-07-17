# stfu — HTPC Volume Control

> Volume control + closed captions for the HTPC. No app install required. Any LAN browser works.

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

Open `http://pluto:5000` from any device on the LAN.

## Changelog

### v4.1.0 (2025-07-16)
**Stability & Version Display**
- Added version badge to web UI (renders from `stfu/__init__.py`)
- **Audio**: Cached pycaw COM interface in `AudioController.__init__` with `threading.Lock` (fixes CoInitialize on every call)
- **Captions**: Added MQTT reconnection with exponential backoff (1s→30s, 10% jitter) + `stop()` method for graceful shutdown
- **Config**: Full validation via `__post_init__` on all dataclasses; unknown TOML keys now warned; `MQTT_BROKER` env var override
- **Overlay**: Fixed bare `except:` → logs error with traceback
- **MCP**: Removed global state; new `create_mcp_server(audio, config)` factory with closure injection
- **Defaults**: Synced `volume.default = 20` in config.py and stfu.toml

### v4.0.0
Initial release — web UI, overlay, MQTT captions, MCP server, Windows service support.

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

The MCP server exposes these tools for AI control:

- `get_volume` — Read current volume/mute state
- `set_volume(percent)` — Set volume 0-100
- `volume_up()` — Increase by step
- `volume_down()` — Decrease by step
- `toggle_mute()` — Toggle mute
- `set_mute(muted)` — Set mute explicitly

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

Edit `stfu.toml` to customize. All values have sensible defaults.

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

- **Audio**: Cached pycaw COM interface in `AudioController.__init__` + added `threading.Lock` for thread safety (was recreating on every call)
- **MQTT**: Added exponential backoff reconnection (1s→30s) in `CaptionCapture` with `_stop_event` for graceful shutdown
- **Config**: Full validation via `__post_init__` on all dataclasses; unknown TOML keys now warned; `MQTT_BROKER` env var override
- **Config**: Fixed volume default mismatch (now `20` in both `stfu.toml` and `config.py`)
- **MCP**: Removed global state; new `create_mcp_server(audio, config)` factory with dependency injection
- **Overlay**: Fixed bare `except: pass` → logs errors with traceback
- **Web UI**: Version badge displayed (`v{{ version }}`)

### v4.0.0
- Initial release: web UI, overlay, MQTT captions, MCP server, Windows service

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

- **Overlay single Tk instance** — `run_overlay()` creates new `Tk()` each call; only one overlay can run per process. Guard or reuse root.
- **Busy-wait loops** — `__main__.py:124` and `service.py:74` use `sleep(1)` polling. Use `threading.Event` for clean shutdown.
- **SSE endpoint unused** — `web.py:/cc/stream` exists but captions use MQTT. Remove or wire up.
- **Per-app volume** — pycaw session API not yet exposed via REST/MCP.

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
- [ ] Voice command intent mapping (e.g., "make it louder" → volume_up)
- [ ] Scheduled volume profiles (night mode, movie mode)
- [ ] LLM-driven caption summarization via MCP

### v2.0 — Cross-platform
- [ ] Linux support (PulseAudio/PipeWire via `pactl` or `wpctl`)
- [ ] macOS support (CoreAudio via `osascript` or `SwitchAudioSource`)
- [ ] Docker image for headless deployment
- [ ] ARM64 builds for Pi/ESP32 edge nodes

## Contributing

1. Fork the repo
2. Create a feature branch
3. Make changes with tests
4. Run `ruff check` and `black --check`
5. Submit PR

## License

MIT — do what you want.