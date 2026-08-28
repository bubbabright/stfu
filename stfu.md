---
title: stfu — HTPC MQTT Architecture
status: done
version: v3
host: pluto
tags: [project, mqtt, htpc, python, esp32, foss, portfolio, vre]
---

# stfu — HTPC MQTT Architecture

> Volume control + closed captions for the HTPC, over MQTT.
> No app install required. Any LAN browser works.
> URL: https://stfu.hoboguppy.com

---

> [!info] Status — Done (2026-06-20)
> Met the use case it was built for — works, runs in terminal. Kay now works away from home, so the original day-to-day need (HTPC captions/volume control while she's around) doesn't come up the same way, but that doesn't make this unfinished — it did its job. ESP32 voice control and the items in TODO below are optional extensions, not required for completion.

---

## Architecture

```
[pluto - Windows 11 HTPC]
  ├── mss + Tesseract (OCR loop)  →  pub: htpc/captions
  ├── pycaw (Windows audio API)   →  pub: htpc/volume/state
  │                               ←  sub: htpc/volume/set
  ├── tkinter (CC overlay)        ←  sub: htpc/captions
  └── Flask (serves browser UI)   → one-time page load, then silent

        ↕ MQTT (192.168.1.215:1883)

[Edge devices — browser / MQTT.js over WebSocket :9001]
  ├── ganymede (phone)
  ├── phobos (tablet)
  ├── ESP32 voice devices (in progress)
  └── any LAN browser
```

## MQTT Topics

| Topic | Direction | Publisher | Subscribers |
|-------|-----------|-----------|-------------|
| `htpc/captions` | HTPC → edges | OCR loop | tkinter · browsers |
| `htpc/volume/state` | HTPC → edges | pycaw | browsers |
| `htpc/volume/set` | edges → HTPC | browsers · ESP32 | pycaw |

## OCR Gate (key design decision)

Tesseract only runs when someone is subscribed to `htpc/captions`.
If no subscribers → mss still grabs frames but Tesseract stays idle.
Efficient. Doesn't waste CPU when nobody needs captions.

```
mss (screen grab)
  → white pixel delta check
  → subscriber check: htpc/captions
      ⛔ no subscribers → Tesseract idle
      ✅ subscribers present → Tesseract OCR → publish
```

## Broker

Mosquitto · Alpine LXC · CT 118 on [[antsy]]
IP: `192.168.1.215:1883` (MQTT) · `:9001` (WebSocket for browsers)
Caddy Layer 4 passthrough on `:8883`

> [!info] CT 118 running (confirmed 2026-06-20 via pve `pct list`)
> Previously documented as stopped — no longer the case. Broker should be reachable for testing without manual start.

## ESP32 Voice Devices (in progress)

Adding voice control for volume via ESP32 + microphone.

**Planned flow:**
```
ESP32 mic → ESPHome wake word (microWakeWord, on-device)
          → command recognized
          → MQTT publish → htpc/volume/set
          → pycaw adjusts audio
```

ESP32 nodes managed via ESPHome (https://esphome.hoboguppy.com).
HA pipeline handles speech intent → MQTT action.

ESP32 publishes to `htpc/volume/set` only — one-way edge device.
Does not need captions or state back.

## Portfolio Value (VR&E)

Demonstrates:
- Pub/sub architecture (MQTT)
- Event-driven design with resource gating
- Python: mss · Tesseract · pycaw · tkinter · Flask
- Cross-device web UI — no native app
- Self-hosted infrastructure
- Physical hardware integration (ESP32)

## Design History

Three deploy models exist as rendered diagrams in
[`docs/diagrams/`](docs/diagrams/), all considered valid — not just draft
iterations toward v3:

- **[v1](docs/diagrams/v1-nircmd.html)** — nircmd CLI for volume, single
  bidirectional `htpc/volume` topic, no OCR gate, no Flask/MQTT split.
  Simplest model — closest analog for a future cross-platform port
  (nircmd's role played by `pactl`/`wpctl` on Linux, see roadmap below).
- **[v2](docs/diagrams/v2-pycaw-gated.html)** — pycaw (Windows Audio API)
  swap-in for volume, 3-way topic split (`captions` / `volume/state` /
  `volume/set`), OCR subscriber-gate introduced, browser edge devices over
  `mqtt.js`/WebSocket.
  Bridges from v1 toward v3's real code.
- **[v3](docs/diagrams/v3-flask-mqtt-split.html)** — what's actually
  shipped. Flask decoupled from MQTT (HTTP serves the page once, then goes
  silent; MQTT carries all live state after that), 3 HTPC services split
  out (Flask / pycaw / tkinter), OCR gate retained from v2. Matches
  `/mnt/nas/projects/stfu/CLAUDE.md`'s module breakdown exactly.

## Possible Future Extensions (optional — project is done as-is)

- [ ] Test ESP32 + ESPHome wake word
- [ ] Wire ESPHome → HA → MQTT → pycaw
- [ ] Draw v4 architecture diagram (add ESP32 voice nodes)
- [ ] Consider M1 STT as alternative to Tesseract OCR for captions
