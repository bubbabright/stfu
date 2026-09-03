# stfu/__main__.py — Main entry point
"""STFU — HTPC Volume Control

Usage:
    python -m stfu                       Run web server + overlay (dev/manual use)
    python -m stfu --no-overlay          Run web server only — the "web" module
    python -m stfu --overlay-only        Run standalone overlay only — the "overlay" module
    python -m stfu --night-light-helper  Run Night Light helper — the "nightlight" module
    python -m stfu --tint-only           Run standalone tint overlay only — the "tint" module
    python -m stfu --mcp                 Run MCP server only (stdio, on-demand, no autostart)

No autostart — each module is started by hand via manage.bat, one process
per module. See CLAUDE.md's Deployment section.
"""
import argparse
import logging
import logging.handlers
import sys
import threading
import time
from pathlib import Path


def setup_logging(config):
    """Configure logging with rotation."""
    log_dir = Path(config.log.file).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    handler = logging.handlers.RotatingFileHandler(
        config.log.file,
        maxBytes=config.log.max_bytes,
        backupCount=config.log.backup_count,
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    )

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))

    root = logging.getLogger()
    root.setLevel(getattr(logging, config.log.level.upper(), logging.INFO))
    root.addHandler(handler)
    root.addHandler(console)


def main():
    parser = argparse.ArgumentParser(description="STFU — HTPC Volume Control")
    parser.add_argument("--no-overlay", action="store_true", help="Disable overlay")
    parser.add_argument("--overlay-only", action="store_true", help="Run standalone overlay only")
    parser.add_argument("--tint-only", action="store_true", help="Run standalone tint overlay only")
    parser.add_argument("--mcp", action="store_true", help="Run MCP server only")
    parser.add_argument(
        "--night-light-helper", action="store_true",
        help="Run Night Light helper (interactive session only, not for --service)",
    )
    parser.add_argument("--config", type=str, help="Path to config file")
    args = parser.parse_args()

    from stfu.config import load_config

    config_path = Path(args.config) if args.config else None
    config = load_config(config_path)

    # Distinct log file per always-on module — each is a separate long-lived
    # process, and two RotatingFileHandlers on the same file race each other
    # on rollover (os.rename while the other holds it open).
    if args.night_light_helper:
        config.log.file = str(Path(config.log.file).with_name("stfu_night_light_helper.log"))
    elif args.overlay_only:
        config.log.file = str(Path(config.log.file).with_name("stfu_overlay.log"))
    elif args.tint_only:
        config.log.file = str(Path(config.log.file).with_name("stfu_tint.log"))

    setup_logging(config)
    log = logging.getLogger("stfu")
    log.info("STFU starting")

    # MCP-only mode — each MCP client owns its own stdio instance, no lock
    if args.mcp:
        from stfu.audio import AudioController
        from stfu.mcp_server import create_mcp_server, start_heartbeat

        audio = AudioController(config)
        mcp = create_mcp_server(audio, config=config)
        start_heartbeat(config)
        log.info("Starting MCP server")
        mcp.run(transport=config.mcp.transport)
        return

    # Night-light-helper mode — must run in the interactive user session;
    # see stfu/night_light_helper.py for why.
    if args.night_light_helper:
        from stfu.night_light_helper import run_night_light_helper
        run_night_light_helper(config)
        return

    # Standalone overlay mode — runs in the interactive user session, since
    # tkinter needs the desktop; started by hand via manage.bat.
    if args.overlay_only:
        from stfu.audio import AudioController
        from stfu.overlay import run_overlay

        audio = AudioController(config)
        log.info("Starting standalone overlay")
        run_overlay(audio, config)
        return

    # Standalone tint mode — same interactive-session constraint as the
    # volume overlay; see stfu/tint.py for why it can't share that window.
    if args.tint_only:
        from stfu.tint import run_tint

        log.info("Starting tint overlay")
        run_tint(config)
        return

    # Normal mode
    from stfu.config import acquire_singleton_lock

    try:
        acquire_singleton_lock(Path(config.log.file).parent / "stfu.lock")
    except RuntimeError as e:
        log.error(str(e))
        print(str(e))
        sys.exit(1)

    from stfu.audio import AudioController
    from stfu.web import create_app
    from stfu.nightlight import HTTPNightlightClient
    from stfu.tint import HTTPTintClient

    audio = AudioController(config)

    nightlight = None
    if config.nightlight.enabled:
        nightlight = HTTPNightlightClient(config)

    tint = None
    if config.tint.enabled:
        tint = HTTPTintClient(config)

    # Flask web server
    app, cc_queue = create_app(audio, config, nightlight=nightlight, tint=tint)

    def _run_flask():
        try:
            app.run(
                host=config.web.host,
                port=config.web.port,
                debug=False,
                use_reloader=False,
                threaded=True,
            )
        except Exception as e:
            log.error("Web server failed to start: %s", e, exc_info=True)

    flask_thread = threading.Thread(target=_run_flask, daemon=True)
    flask_thread.start()
    log.info("Web server: http://%s:%d", config.web.host, config.web.port)
    print(f"STFU running: http://{config.web.host}:{config.web.port}")

    # Overlay
    if config.overlay.enabled and not args.no_overlay:
        try:
            from stfu.overlay import run_overlay

            overlay_thread = threading.Thread(
                target=run_overlay, args=(audio, config), daemon=True
            )
            overlay_thread.start()
            log.info("Overlay started")
        except Exception as e:
            log.warning("Overlay unavailable: %s", e)

    # Caption capture
    if config.cc.enabled:
        try:
            from stfu.captions import CaptionCapture

            cc = CaptionCapture(config)
            cc_thread = threading.Thread(target=cc.start, daemon=True)
            cc_thread.start()
            log.info("Caption capture started")
        except Exception as e:
            log.warning("Captions unavailable: %s", e)

    # Keep alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("STFU stopped")
        print("\nStopped.")


if __name__ == "__main__":
    main()
