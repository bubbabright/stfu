# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

STFU — a Windows-only HTPC volume control + closed-caption tool. Runs on a Windows 11 media PC ("pluto"), exposes volume control via a REST web UI, an on-screen overlay, MQTT pub/sub for edge devices (phone/tablet/ESP32), and an MCP server for AI-driven control. No test suite or lint config currently exists in the repo despite references to them in README.md — verify before relying on `pytest`/`ruff`/`black` commands.

## Deployment

Live instance runs on `pluto` (Windows 11 HTPC). Reach it with `ssh pluto`. `C:\scripts\stfu` on pluto is a **separate git clone** of this same repo (github.com/bubbabright/stfu) — not shared NAS storage. Editing files here does NOT change what pluto sees; deploy by committing here, `git push`, then `ssh pluto` and `git pull` (check `git status`/`git diff` there first — pluto's working tree can carry its own uncommitted edits). After pulling, the running processes still need restarting manually — see below.

**No autostart, on purpose.** Scheduled Tasks were tried and dropped (2026-08-29/30) — pluto runs for weeks between reboots, so autostart-on-boot reliability wasn't worth what it cost: `Stop-ScheduledTask` silently leaving the old python.exe process tree alive, and one night every one of the three module tasks turned up double-running (web/overlay/night-light-helper each had 2 live processes; task/trigger/action definitions were each verified singular, no Startup-folder or Run-key culprit found — cause never conclusively identified). All three tasks were deleted. Daniel starts STFU by hand each session via `manage.bat`.

**Modularity is a deliberate, valued property of this app — not incidental, don't collapse it.** Web/overlay/night-light-helper stay three separately-launchable processes even though nothing forces that anymore now that everything runs from the interactive session by hand (the old SYSTEM-vs-interactive-session split that originally forced the theme/nightlight helper into its own process is gone, but the module boundary itself should stay). Reason: this app is still under active development on two fronts that need the pieces to stay independently swappable —
- **REST → MQTT migration in progress.** Volume/theme/nightlight control currently goes over REST (`web.py`); the plan is to run REST and MQTT in parallel during the transition, then likely retire REST once MQTT covers everything. `mqtt.topic_volume_state`/`topic_volume_set` already exist in `config.py` but nothing subscribes to them yet — that's this migration's landing spot, not dead code to clean up.
- **Linux port planned.** The app is Windows-only today (pycaw/comtypes/tkinter/`winreg`), but cross-platform support is on the roadmap.

Keep new functionality along these same lines — a new capability gets its own mode/flag rather than being folded into an existing one, unless there's a concrete reason to share a process. Prefer designs that let a piece (e.g. the transport, or a platform-specific controller) be swapped or pulled out wholesale rather than threaded through everything else.

## Commands

```bat
setup.bat   # uv venv + install deps (no task registration — see Deployment)
manage.bat  # menu: start/stop each module by hand, or all of them, or check status

python -m stfu                       # web + overlay + captions in one process (dev/manual use only)
python -m stfu --no-overlay          # the "web" module
python -m stfu --overlay-only        # the "overlay" module
python -m stfu --night-light-helper  # the "theme"/"nightlight" module — interactive session only
python -m stfu --mcp                 # MCP server (stdio, on-demand)
python -m stfu --config path.toml    # override config file path
```

The app is Windows-only (pycaw/comtypes for audio, tkinter overlay) — it will not run on Linux/macOS. There is no test or lint tooling pinned in `requirements.txt`. The Python environment is managed by `uv` — one canonical `.venv`, not a per-tool venv sprawl.

## Architecture

Single entry point, one run mode per module (see the Deployment table), all sharing the same `AppConfig`:

- `stfu/__main__.py` — argparse dispatch. Bare `python -m stfu` (no flags) starts Flask, overlay, and captions all in one process on daemon threads, then busy-waits (`sleep(1)` loop) until `KeyboardInterrupt` — convenient for local dev/manual testing, not how it's deployed. `--mcp`, `--night-light-helper`, and `--overlay-only` each bypass that and hand off entirely to their own function (`mcp_server.create_mcp_server`, `night_light_helper.run_night_light_helper`, `overlay.run_overlay`) — these are the actual production modules, each started by hand via `manage.bat` (see Deployment — modularity here is intentional, don't merge these).
- `stfu/config.py` — one `@dataclass` per `stfu.toml` section (`VolumeConfig`, `WebConfig`, `OverlayConfig`, `MQTTConfig`, `CCConfig`, `ThemeConfig`, `NightLightConfig`, `MCPConfig`, `LogConfig`), composed into `AppConfig`. Each dataclass self-validates in `__post_init__` (range/positivity checks) and raises `ValueError` on bad values — config errors are fail-fast at startup, not silently clamped. `load_config()` reads TOML, deep-merges it over the dataclass defaults section-by-section, and warns (not errors) on unknown TOML keys via `VALID_KEYS`. `MQTTConfig.broker` defaults from the `MQTT_BROKER` env var, everything else only from TOML/defaults. `ThemeConfig.show_in_ui` (default `False`) hides the Dark Mode button from the web UI without touching the backend routes — added for exactly that: keep something wired but not surfaced.
- `stfu/audio.py` — `AudioController` wraps pycaw. COM is initialized and the `EndpointVolume` interface is cached once in `__init__` (not per-call — this was a real perf fix, see README changelog), guarded by a `threading.Lock` since it's shared across the Flask thread, overlay thread, and MCP tool calls.
- `stfu/web.py` — `create_app(audio, theme, config, nightlight=None)` factory returns `(Flask app, cc_queue)`. All routes read/mutate state through the injected controllers, no module-level globals. `/cc/stream` (SSE) exists but is currently unused — captions ship over MQTT instead, not this endpoint. `/theme`+`/theme/dark-mode` and `/nightlight` each relay to the interactive-session helper via their respective HTTP client and return `503` if it's unreachable — never a silent no-op.
- `stfu/mcp_server.py` — `create_mcp_server(audio, theme=None, config=...)` factory using FastMCP, same dependency-injection pattern as `web.py`. Exposes `get_volume`/`set_volume`/`volume_up`/`volume_down`/`toggle_mute`/`set_mute`, plus `get_dark_mode`/`toggle_dark_mode` when `theme` is not `None`. `init_mcp()`/`get_mcp()` are a deprecated module-global shim kept only for backward compat — new code should use `create_mcp_server()` directly.
- `stfu/theme.py` — Windows **Dark Mode** control (Settings > Personalization > Colors). `ThemeController` writes `HKCU\...\Themes\Personalize`'s `AppsUseLightTheme`/`SystemUsesLightTheme` DWORDs and broadcasts `WM_SETTINGCHANGE` so Explorer/apps repaint immediately. `HTTPThemeClient` is an HTTP client with the same interface, used by every run mode except the helper.
- `stfu/nightlight.py` — the actual Windows **Night Light** blue-light filter, a separate feature from Dark Mode above. Its registry state is an undocumented, version-fragile binary blob, so this shells out to an off-the-shelf CLI (`wnl`, path in `config.nightlight.wnl_path`) instead of hand-patching it. `NightLightController` runs `wnl status|on|off` via `subprocess` and parses stdout. `HTTPNightlightClient` reuses the theme helper's port/timeout config since it's the same interactive-session process (see next entry).
- `stfu/night_light_helper.py` — `run_night_light_helper(config)`, dispatched via `--night-light-helper`. The **only** place `ThemeController` and `NightLightController` are ever constructed — both need `HKEY_CURRENT_USER`, which is scoped to the caller's logon session. Every other run mode reaches them over HTTP through `HTTPThemeClient`/`HTTPNightlightClient`. Same underlying constraint the tkinter overlay already works around (a headless/SYSTEM process can't touch the interactive desktop either) — a separate interactive-session process, reached over HTTP instead of touched directly.
- `stfu/overlay.py` — tkinter on-screen volume display, polls `AudioController` on a timer. `run_overlay()` creates a fresh `Tk()` each call — only one overlay can run per process (known limitation, not currently guarded). Dispatched via `--overlay-only` — its own process, not bundled into the web module, since it needs the interactive session the same way the theme/nightlight helper does.
- `stfu/captions.py` — `CaptionCapture` grabs screen frames with `mss`, OCRs with Tesseract, publishes to MQTT (`htpc/captions`). Key design point: it checks MQTT subscriber presence before running Tesseract, so OCR only burns CPU when something is actually listening for captions. Reconnects to the broker with exponential backoff (1s→30s, jittered) and has a `_stop_event`/`stop()` for clean shutdown. Currently started as a thread inside whichever process has `cc.enabled = true` (off by default) — note this thread would need the same session-scoped treatment as overlay/theme if ever run inside the `STFU_Web` (SYSTEM) module, since `mss` also needs desktop access; not yet split into its own module since it's dormant.

State flows one way through MQTT: `pycaw` (this app) is the source of truth for volume, publishing to `htpc/volume/state`; edge devices (browsers via MQTT-over-WebSocket, ESP32 nodes) publish commands to `htpc/volume/set` which this app subscribes to. Caption text flows `mss`/Tesseract → `htpc/captions` → tkinter overlay + browsers.

`archive/` is legacy pre-rewrite code (gitignored) — not part of the active package, don't treat it as current architecture reference.
