# stfu/__main__.py — Main entry point
"""STFU — HTPC Volume Control

Usage:
    python -m stfu              Run web server + overlay
    python -m stfu --no-overlay Run web server only
    python -m stfu --mcp        Run MCP server only
    python -m stfu --service    Run as Windows service
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
    parser.add_argument("--mcp", action="store_true", help="Run MCP server only")
    parser.add_argument("--service", action="store_true", help="Run as Windows service")
    parser.add_argument("--config", type=str, help="Path to config file")
    args = parser.parse_args()

    from stfu.config import load_config

    config_path = Path(args.config) if args.config else None
    config = load_config(config_path)

    setup_logging(config)
    log = logging.getLogger("stfu")
    log.info("STFU starting")

    # MCP-only mode
    if args.mcp:
        from stfu.audio import AudioController
        from stfu.mcp_server import init_mcp, mcp

        audio = AudioController(config)
        init_mcp(audio, config)
        log.info("Starting MCP server")
        mcp.run(transport=config.mcp.transport)
        return

    # Service mode
    if args.service:
        from stfu.service import _service_main
        _service_main()
        return

    # Normal mode
    from stfu.audio import AudioController
    from stfu.web import create_app

    audio = AudioController(config)

    # Flask web server
    app, cc_queue = create_app(audio, config)
    flask_thread = threading.Thread(
        target=lambda: app.run(
            host=config.web.host,
            port=config.web.port,
            debug=False,
            use_reloader=False,
            threaded=True,
        ),
        daemon=True,
    )
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
