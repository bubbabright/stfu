# Robustness hardening: single-instance guard, silent-failure logging, overlay heartbeat

## Goal
Fix the code-level gaps that let today's live-pluto mess happen silently:
no singleton guard (two `--service` processes ran concurrently), no error
handling around the Flask thread (a port-bind failure dies silently), and
no liveness signal from the overlay (it's been dead ~24 days with zero log
trace). Ship the fix; do not touch the live pluto processes as part of
this — that's a separate, confirmed-with-Daniel action (see report).

## Acceptance criteria
- [ ] Second `python -m stfu` / `--service` invocation refuses to start
      (clear log message + non-zero exit), doesn't silently coexist with
      an already-running instance.
- [ ] If the Flask thread fails to start (e.g. port in use), it's logged
      at ERROR with the exception — not silently swallowed by the daemon
      thread.
- [ ] Overlay crashes (anything past initial `Tk()` construction, e.g. a
      `mainloop()`-level failure) get logged instead of the thread dying
      silently.
- [ ] Overlay logs a periodic liveness line (throttled, not every 200ms
      tick) so "is the overlay alive" is answerable from `stfu.log` alone.

## Scope
In: `stfu/config.py` (new `acquire_singleton_lock()`), `stfu/__main__.py`,
`stfu/service.py`, `stfu/overlay.py`.
Out: `stfu/web.py` route logic, `stfu/audio.py`, `stfu/captions.py`,
`stfu/mcp_server.py`, anything on pluto itself (no ssh actions here).

## Self-check
1. closer to goal: yes — directly prevents the duplicate-process class of
   bug that caused today's investigation, and turns "overlay silently
   dead for 24 days" into "overlay dead, logged, visible."
2. maintenance: net positive — replaces silent failure with visible
   failure, no new moving parts to maintain.
3. baggage: cut — no new file-based heartbeat/JSON side-channel (that's
   what caused the legacy-artifact confusion in the first place); reuse
   the existing `logging` setup instead.
4. infra: reused — `msvcrt` (stdlib, already Windows-only app) for the
   lock, existing `logging` module for heartbeat/error visibility. No new
   dependency.

## Steps (all independent of each other, single file each mostly)
1. `stfu/config.py`: add `acquire_singleton_lock(lock_path) -> None`,
   raises `RuntimeError` if another instance already holds the lock.
   Uses `msvcrt.locking()` on an exclusively-held file handle — released
   automatically by the OS on process exit/crash, no stale-lock cleanup
   needed (important given this app's history of ungraceful termination).
2. `stfu/__main__.py`: call the lock in normal-mode `main()` right after
   `load_config()`, before starting Flask/overlay/captions. Wrap the
   Flask-thread target in a named function with try/except logging
   instead of a bare lambda.
3. `stfu/service.py`: same lock call in `_service_main()`, same Flask
   thread error-handling fix (duplicate ~10 lines rather than a new
   shared-startup abstraction — out of scope per self-check #3).
4. `stfu/overlay.py`: wrap all of `run_overlay()`'s body (not just the
   per-tick `update()`) in try/except with logging. Add a throttled
   heartbeat log line (every ~5 min) inside `update()`.

## Delegate
Not delegated — single-session direct execution (Claude already holds
full context from live pluto investigation; re-explaining to opencode
would cost more than it saves). See LEARNINGS.md 2026-08-12 entry for the
established pattern this follows.
