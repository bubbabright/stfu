# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

STFU — a Windows-only HTPC volume control + closed-caption tool. Runs on a Windows 11 media PC ("pluto"), exposes volume control via a REST web UI, an on-screen overlay, MQTT pub/sub for edge devices (phone/tablet/ESP32), and an MCP server for AI-driven control. No test suite or lint config currently exists in the repo despite references to them in README.md — verify before relying on `pytest`/`ruff`/`black` commands.

## Deployment

Live instance runs on `pluto` (Windows 11 HTPC). Reach it with `ssh pluto`. `C:\scripts\stfu` on pluto and this repo's checkout are the **same underlying storage** (NAS-backed), not two separate clones — editing files here changes what pluto sees immediately. Only the Python environment (`.venv`) and running processes are actually per-machine state.

No NSSM, no Windows Service. Autostart is three Windows Scheduled Tasks, one per module, registered by `scripts/register_task.ps1 -Module <web|overlay|night-light-helper>` (called for all three by `setup.bat`, or individually via `manage.bat`):

| Task | Module | Trigger | Principal | Why |
|---|---|---|---|---|
| `STFU_Web` | `--no-overlay` | At startup | `SYSTEM` | Volume control must work headlessly — pluto has `AutoAdminLogon` disabled, so nothing "at logon" is guaranteed to run promptly after a reboot. |
| `STFU_Overlay` | `--overlay-only` | At logon | interactive user | tkinter needs the desktop session. |
| `STFU_NightLightHelper` | `--night-light-helper` | At logon | interactive user | `HKEY_CURRENT_USER`/`WM_SETTINGCHANGE` are session-scoped — see `stfu/theme.py`. |

Each registration script run is idempotent (unregisters any existing task of that name first) and sets `WorkingDirectory`/`Principal` explicitly — an earlier ad-hoc overlay task got both wrong (blank `WorkingDirectory` silently resolved to the wrong Python on PATH), which is why this exists as one shared, parameterized script instead of one-off registrations.

## Commands

```bat
setup.bat                            # uv venv + install + register all 3 tasks
manage.bat                           # interactive menu (start/stop/status per task)

python -m stfu                       # web + overlay in one process (dev/manual use only)
python -m stfu --no-overlay          # the "web" module
python -m stfu --overlay-only        # the "overlay" module
python -m stfu --night-light-helper  # the "theme" module — interactive session only
python -m stfu --mcp                 # MCP server (stdio, on-demand, no autostart)
python -m stfu --config path.toml    # override config file path
```

The app is Windows-only (pycaw/comtypes for audio, tkinter overlay) — it will not run on Linux/macOS. There is no test or lint tooling pinned in `requirements.txt`. The Python environment is managed by `uv` — one canonical `.venv`, not a per-tool venv sprawl.

## Architecture

Single entry point, one run mode per module (see the Deployment table), all sharing the same `AppConfig`:

- `stfu/__main__.py` — argparse dispatch. Bare `python -m stfu` (no flags) starts Flask, overlay, and captions all in one process on daemon threads, then busy-waits (`sleep(1)` loop) until `KeyboardInterrupt` — convenient for local dev/manual testing, not how it's deployed. `--mcp`, `--night-light-helper`, and `--overlay-only` each bypass that and hand off entirely to their own function (`mcp_server.create_mcp_server`, `night_light_helper.run_night_light_helper`, `overlay.run_overlay`) — these are the actual production modules, each its own Scheduled Task.
- `stfu/config.py` — one `@dataclass` per `stfu.toml` section (`VolumeConfig`, `WebConfig`, `OverlayConfig`, `MQTTConfig`, `CCConfig`, `MCPConfig`, `LogConfig`), composed into `AppConfig`. Each dataclass self-validates in `__post_init__` (range/positivity checks) and raises `ValueError` on bad values — config errors are fail-fast at startup, not silently clamped. `load_config()` reads TOML, deep-merges it over the dataclass defaults section-by-section, and warns (not errors) on unknown TOML keys via `VALID_KEYS`. `MQTTConfig.broker` defaults from the `MQTT_BROKER` env var, everything else only from TOML/defaults.
- `stfu/audio.py` — `AudioController` wraps pycaw. COM is initialized and the `EndpointVolume` interface is cached once in `__init__` (not per-call — this was a real perf fix, see README changelog), guarded by a `threading.Lock` since it's shared across the Flask thread, overlay thread, and MCP tool calls.
- `stfu/web.py` — `create_app(audio, theme, config)` factory returns `(Flask app, cc_queue)`. All routes read/mutate state through the injected `AudioController`/theme client, no module-level globals. `/cc/stream` (SSE) exists but is currently unused — captions ship over MQTT instead, not this endpoint. `/theme` and `/theme/dark-mode` relay to `night_light_helper.py` via the injected theme client and return `503` if it's unreachable — never a silent no-op.
- `stfu/mcp_server.py` — `create_mcp_server(audio, theme=None, config=...)` factory using FastMCP, same dependency-injection pattern as `web.py`. Exposes `get_volume`/`set_volume`/`volume_up`/`volume_down`/`toggle_mute`/`set_mute`, plus `get_dark_mode`/`toggle_dark_mode` when `theme` is not `None`. `init_mcp()`/`get_mcp()` are a deprecated module-global shim kept only for backward compat — new code should use `create_mcp_server()` directly.
- `stfu/theme.py` — Windows Dark Mode control (Settings > Personalization > Colors), not the unrelated Night Light blue-light filter (that one's state is an undocumented, version-fragile binary registry blob — deliberately not used). `ThemeController` writes `HKCU\...\Themes\Personalize`'s `AppsUseLightTheme`/`SystemUsesLightTheme` DWORDs and broadcasts `WM_SETTINGCHANGE` so Explorer/apps repaint immediately. `HTTPThemeClient` is an HTTP client with the same interface, used by every run mode except the helper — see next entry for why.
- `stfu/night_light_helper.py` — `run_night_light_helper(config)`, dispatched via `--night-light-helper`, the `STFU_NightLightHelper` module. The **only** place `ThemeController` is ever constructed. Must run in the interactive desktop session — `HKEY_CURRENT_USER` and `WM_SETTINGCHANGE` are scoped to the caller's logon session, and the `STFU_Web` module runs as `SYSTEM`/at-startup, which can reach neither — a `ThemeController` there would silently write to the wrong registry hive and broadcast to nobody. Same underlying constraint the tkinter overlay already works around (SYSTEM can't render on the interactive desktop either) — this follows the same shape, a separate interactive-session process, reached over HTTP instead of touched directly.
- `stfu/overlay.py` — tkinter on-screen volume display, polls `AudioController` on a timer. `run_overlay()` creates a fresh `Tk()` each call — only one overlay can run per process (known limitation, not currently guarded). Dispatched via `--overlay-only`, the `STFU_Overlay` module — its own Scheduled Task, not bundled into the web module, since it needs the interactive session the same way the theme helper does.
- `stfu/captions.py` — `CaptionCapture` grabs screen frames with `mss`, OCRs with Tesseract, publishes to MQTT (`htpc/captions`). Key design point: it checks MQTT subscriber presence before running Tesseract, so OCR only burns CPU when something is actually listening for captions. Reconnects to the broker with exponential backoff (1s→30s, jittered) and has a `_stop_event`/`stop()` for clean shutdown. Currently started as a thread inside whichever process has `cc.enabled = true` (off by default) — note this thread would need the same session-scoped treatment as overlay/theme if ever run inside the `STFU_Web` (SYSTEM) module, since `mss` also needs desktop access; not yet split into its own module since it's dormant.

State flows one way through MQTT: `pycaw` (this app) is the source of truth for volume, publishing to `htpc/volume/state`; edge devices (browsers via MQTT-over-WebSocket, ESP32 nodes) publish commands to `htpc/volume/set` which this app subscribes to. Caption text flows `mss`/Tesseract → `htpc/captions` → tkinter overlay + browsers.

`archive/` is legacy pre-rewrite code (gitignored) — not part of the active package, don't treat it as current architecture reference.
