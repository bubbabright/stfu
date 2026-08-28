# stfu — PM Status

Onboarded: 2026-08-12. Sources checked: README.md, CLAUDE.md (written this
session), stfu.toml, all 9 modules in `stfu/` (read directly, not
delegated — project is small, 1071 lines total), `git log`, `git status`,
git diff content, obsidian pointer stub at
`04-bubbAlab/03-projects/pointers/stfu.md`.

## What exists

Windows-only HTPC volume control + closed captions. Flask REST API, tkinter
overlay, MQTT pub/sub for edge devices (phone/tablet/ESP32-planned), FastMCP
server for AI control. Runs on `pluto` (Windows 11 HTPC), reachable via
`ssh pluto`. Deep architecture notes in `/mnt/nas/projects/stfu/CLAUDE.md`
(just written) — read that first for module-by-module detail, not repeated
here.

Project status per its own doc (`stfu.md`, canonical home confirmed by the
obsidian pointer stub — obsidian's copy is a redirect stub, not a
duplicate): **done**. Met its original use case; ESP32 voice control and
README's roadmap items are optional extensions, not required for
completion.

## Docs-vs-code gaps found

- README's Development section (`pip install -e .[dev]`, `pytest tests/`,
  `ruff check`, `black`) doesn't work as written — no `pyproject.toml`,
  no `setup.py`, no `tests/` dir, no ruff/black in `requirements.txt`.
  Those commands are aspirational, not real. Flagged in CLAUDE.md already.
- README's "Known Issues" section (overlay single-`Tk()`-per-process,
  busy-wait `sleep(1)` polling in `__main__.py:124` and `service.py:74`,
  unused `/cc/stream` SSE endpoint, no per-app volume via pycaw sessions) —
  verified accurate against current code, not stale.
- README's roadmap (v1.2 observability, v1.3 features, v1.4 AI/automation,
  v2.0 cross-platform) — none of it has code yet. Purely aspirational list.

## Uncommitted working-tree state (as of 2026-08-12)

- All 9 `stfu/*.py` files + several root files show as modified in
  `git status`, but `git diff --stat` shows 0 insertions/deletions for all
  of them except `README.md` and `stfu.toml` — the rest are pure
  `100644 → 100755` mode (chmod +x) changes, no content change. Likely a
  NAS/CIFS mount artifact, not a real edit. Low priority, not investigated
  further.
- `README.md` content has been passed through a terseness/compression pass
  (articles and filler dropped throughout — e.g. "Volume control + closed
  captions for the HTPC" → "Volume control + closed caption for HTPC").
  This matches the `caveman-compress` skill's behavior exactly, including
  the human-readable backup it leaves behind — `backups/README.original.md`
  is that backup. Intentional prior skill run, not corruption. Not reverted.
- Untracked and new: `.github/workflows/opencode.yml` (GH Action, triggers
  opencode on `/oc` PR/issue comments — installed, not yet exercised),
  `CLAUDE.md` (written this session), `backups/` (holds the README
  pre-compression backup above).
- None of the above has been committed. Nothing in this list blocks
  anything — noted for continuity, not because it needs fixing.

## git history

7 commits. Latest real work: `d40d8d9` (overlay status + version badge
template fix), `e4bb328` (indent fix), `7ec1d13` tagged as "Release
v4.1.0". No branches beyond the working tree's uncommitted state above.

## Live pluto findings (2026-08-12, robustness review — see git log / diff
for the code fix, this section is the operational picture)

Diagnosed via `ssh pluto` (real prompt: "review project code — ensure
robustness. Example: overlay is currently down"). Deployed state has
drifted hard from the git-tracked package:

- **3 processes touching the same pycaw audio endpoint right now**: a
  27-day-old orphaned legacy process (`python C:\scripts\stfu\app.py`,
  PID 18400 at investigation time — that exact file no longer exists,
  moved to `C:\scripts\stfu-backup-20260716\` during the July 16 rewrite
  migration but the running process never got killed), plus two duplicate
  `venv-windows\...\python.exe -m stfu --service` processes under the one
  NSSM "STFU" service — leaked during a ~30min NSSM crash-loop on July 16
  (`ModuleNotFoundError: No module named 'flask'` — NSSM was pointed at a
  Python without Flask installed before being fixed to use the venv).
- **`STFUOverlay` Scheduled Task** — points at `overlay_helper.py`, part of
  the pre-rewrite legacy layout, deleted on July 16. Broken today
  regardless of trigger. Fully redundant now — the current service starts
  its own overlay thread.
- Legacy artifacts `control.json` / `overlay_heartbeat.json` in
  `C:\scripts\stfu\` are NOT written by any code in the current package or
  even in the legacy backup's `.py` files (checked all of them) — source
  never conclusively identified, likely another vestigial piece. Not
  relevant to current-package health; don't use their presence as a signal
  in future debugging.
- Fixed in code (see `.pm/work-robustness-hardening-20260812-1530.md`):
  singleton-lock guard, Flask-thread error logging, overlay crash logging
  + throttled heartbeat log line. NOT fixed: the actual live zombie
  processes / stale scheduled task on pluto — that needs Daniel's OK
  before killing anything, since one of those processes may currently be
  the one actually serving working volume control.

## Design history (this session's actual task)

Found 3 rendered architecture diagrams in
`/mnt/nas/obsidian/03-llm-history/Conversations/_Unsorted/`:
`mqtt-architecture.html` (v1: nircmd-based volume, single bidirectional
`htpc/volume` topic), `-v2.html` (pycaw swap-in, 3-way topic split, OCR
subscriber-gate added), `-v3.html` (Flask/MQTT decoupled into 3 HTPC
services — matches what's actually shipped in `stfu/` today). Daniel
confirmed: all 3 are valid deploy models, not just discard-2-keep-1 drafts.
Relocating them into the project as documented design history rather than
leaving them in an `_Unsorted` chat-export folder — see work-doc for this
task.
