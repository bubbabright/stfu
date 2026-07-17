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
