# stfu/service.py — Windows service wrapper
# NSSM setup:
#   nssm install STFU python -m stfu --service
#   nssm set STFU AppDirectory C:/scripts/stfu
#   nssm set STFU DisplayName "STFU Volume Control"
#   nssm set STFU Start SERVICE_AUTO_START
#   nssm set STFU AppStdout C:/scripts/stfu/logs/service-stdout.log
#   nssm set STFU AppStderr C:/scripts/stfu/logs/service-stderr.log
#   nssm start STFU
import logging
import sys
import time

from stfu.config import load_config
from stfu.audio import AudioController
from stfu.web import create_app

log = logging.getLogger("stfu.service")

# Service control events
_STOPPING = False


def _service_main():
    """Main entry point for service mode."""
    config = load_config()
    audio = AudioController(config)

    # Start Flask
    app, cc_queue = create_app(audio, config)
    import threading

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
    log.info("Web server started on %s:%d", config.web.host, config.web.port)

    # Start overlay if enabled and display available
    if config.overlay.enabled:
        try:
            import tkinter
            from stfu.overlay import run_overlay

            overlay_thread = threading.Thread(
                target=run_overlay, args=(audio, config), daemon=True
            )
            overlay_thread.start()
            log.info("Overlay started")
        except Exception as e:
            log.warning("Overlay unavailable: %s", e)

    # Start caption capture if enabled
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
    log.info("STFU service running")
    while not _STOPPING:
        time.sleep(1)


try:
    import win32serviceutil
    import win32event
    import win32api

    class STFUService(win32serviceutil.ServiceFramework):
        _svc_name_ = "STFU"
        _svc_display_name_ = "STFU Volume Control"
        _svc_description_ = "HTPC volume control with web UI, overlay, and MCP"

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)

        def SvcStop(self):
            global _STOPPING
            _STOPPING = True
            self.ReportServiceStatus(win32serviceutil.SERVICE_STOP_PENDING)
            win32event.SetEvent(self.stop_event)

        def SvcDoRun(self):
            _service_main()

    if __name__ == "__main__":
        win32serviceutil.HandleCommandLine(STFUService)

except ImportError:
    # Not on Windows or pywin32 not installed — just run directly
    if __name__ == "__main__":
        _service_main()
