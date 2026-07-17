# stfu/overlay.py — tkinter transparent volume overlay
import logging
import time
import tkinter as tk

log = logging.getLogger("stfu.overlay")


def run_overlay(audio, config):
    """Run transparent fullscreen overlay showing volume/mute status."""
    cfg = config.overlay

    root = tk.Tk()
    root.title("STFU Overlay")
    root.attributes("-topmost", True)
    root.attributes("-transparentcolor", "black")
    root.overrideredirect(True)

    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    root.geometry(f"{screen_w}x{screen_h}+0+0")

    canvas = tk.Canvas(root, bg="black", highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    # Persistent mute indicator (red)
    mute_id = canvas.create_text(
        screen_w // 2,
        int(screen_h * 0.76),
        text="",
        fill="#ff5555",
        font=(cfg.font_family, cfg.font_size_mute, "bold"),
        justify="center",
        anchor="center",
    )

    # Transient feedback (white)
    transient_id = canvas.create_text(
        screen_w // 2,
        int(screen_h * 0.76) + 115,
        text="",
        fill="#ffffff",
        font=(cfg.font_family, cfg.font_size_transient, "bold"),
        justify="center",
        anchor="center",
    )

    last_volume = 50
    last_muted = False
    last_action = ""
    last_action_ts = 0.0

    def update():
        nonlocal last_volume, last_muted, last_action, last_action_ts

        try:
            state = audio.get_state()
            volume = state["volume"]
            muted = state["muted"]
            action = state["action"]
            action_ts = state["action_ts"]
            now = time.time()

            # Persistent mute (red)
            if muted:
                canvas.itemconfig(mute_id, text="MUTED")
                root.attributes("-alpha", cfg.opacity)
            else:
                canvas.itemconfig(mute_id, text="")

            # Transient feedback (white)
            show_transient = (
                action
                and action != "MUTED"
                and (now - action_ts) < cfg.transient_duration
            )

            if show_transient:
                if action.startswith("UNMUTED"):
                    canvas.itemconfig(transient_id, text="UNMUTED")
                else:
                    canvas.itemconfig(transient_id, text=action)
                root.attributes("-alpha", cfg.opacity)
            else:
                canvas.itemconfig(transient_id, text="")

            # Hide when nothing to show
            if not muted and not show_transient:
                root.attributes("-alpha", 0.0)

            last_volume = volume
            last_muted = muted

        except Exception as e:
            log.error("Overlay update error: %s", e, exc_info=True)

        root.after(cfg.poll_interval_ms, update)

    log.info("Overlay started")
    update()
    root.mainloop()
