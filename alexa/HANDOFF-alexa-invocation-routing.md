# HANDOFF: Alexa custom skill not routing to endpoint despite all-green build

## Goal (from original plan)
Say "Alexa, ask computer control to mute" on a physical Echo Dot → POST hits our
HTTPS endpoint → MQTT message published. Endpoint infra is proven working
end-to-end via manual tests. The skill will not invoke from the real device
(or from Alexa's own SMAPI simulate-skill API). Diagnose why, don't just retry.

## Architecture
- Echo Dot (**1st generation**, released 2016 — see Leading Hypothesis) →
  Alexa Custom Skill "Computer Control"
  (`amzn1.ask.skill.55f7c9cc-a0b0-41ff-a8f9-f00d6d5fcb78`) → HTTPS endpoint
  `https://stfu.hoboguppy.xyz/alexa` → Caddy `reverse_proxy 127.0.0.1:8000`
  on Oracle VM `spaceguppy` → gunicorn + Flask + `flask-ask-sdk`
  `SkillAdapter` → on `MuteIntent`, publishes MQTT `homelab/pc/office/command`
  (this is a standalone test topic — NOT the real STFU app's
  `htpc/volume/set` on broker `192.168.1.215`; that wiring is deliberately
  deferred).
- Skill package source of truth now lives at
  `/mnt/nas/projects/stfu/alexa/skill-package/` (pulled via
  `ask smapi export-package`, pushed via `ask smapi set-interaction-model` —
  ask-cli 2.30.7, configured on hyperion, vendor id `M108F2SS8X797I`).
- Backend source at `/opt/alexa-mqtt/` on spaceguppy (`app.py`, `wsgi.py`),
  run via `nohup gunicorn wsgi:app -b 127.0.0.1:8000 > /tmp/alexa-mqtt.log 2>&1 &`.

## Confirmed working (verified empirically, don't re-check these)
1. OCI security list: TCP 80/443 open 0.0.0.0/0; firewalld path clear.
2. DNS + TLS: `curl -i https://stfu.hoboguppy.xyz` → 200 via Caddy/Let's Encrypt.
3. MQTT path Oracle→Tailscale→broker→dashboard: manual `mosquitto_pub` from
   spaceguppy showed up instantly on the existing `mqtt.hoboguppy.com` dashboard.
4. Backend code is structurally correct: uses `flask-ask-sdk`'s `SkillAdapter`
   (not the broken `WebserviceSkillHandler`+gunicorn pattern from the original
   plan, which has no WSGI `__call__` at all — confirmed via official Amazon
   docs). Local smoke test: `GET /` → 404, `POST /alexa` unsigned → 400
   (signature verification is genuinely active, not bypassed).
5. `ask smapi get-skill-status` (both `interactionModel` and `manifest`
   resources): all steps `SUCCEEDED` — `LANGUAGE_MODEL_QUICK_BUILD`,
   `LANGUAGE_MODEL_FULL_BUILD`, `DIALOG_MODEL_BUILD`, `NAME_FREE_INTERACTION_BUILD`.
6. `ask smapi get-skill-enablement-status -s <id> -g development` → HTTP
   `204` (enablement exists for the customerId behind the CLI's auth token,
   i.e. the developer account used for `ask configure` on hyperion).
7. `skill-package/skill.json`: endpoint `https://stfu.hoboguppy.xyz/alexa`,
   `sslCertificateType: Wildcard`, NA region set correctly.
8. Interaction model structure valid: `invocationName: "computer control"`,
   `MuteIntent` with samples, standard `AMAZON.HelpIntent/CancelIntent/
   StopIntent/NavigateHomeIntent`.

## Failures observed, in order (this is the actual mystery)
**A.** First web-console-simulator test: request DID reach the backend
(gunicorn log showed activity) but failed signature verification —
`VerificationException: Missing Signature/Certificate for the skill request`
raised in `ask_sdk_webservice_support/verifier.py` (neither `Signature` nor
`SignatureCertChainUrl` header found, case-insensitive, among forwarded
headers). Confirmed `flask_ask_sdk`'s `dispatch_request()` does forward the
full `flask_request.headers` to the verifier, so this isn't an obvious
plumbing bug on our side — headers seemingly were genuinely absent from what
Alexa sent, or got stripped somewhere between Alexa and Flask.

**B.** Second web-simulator attempt (after adding debug header-dump logging
to `app.py` and restarting gunicorn): different failure — "I don't see a
computer control feature available right now." — and gunicorn log showed
**zero new activity**, i.e. this request never reached the backend at all.
Unexplained why this attempt differed from A.

**C.** Physical Echo Dot test #1 (invocation name was "shut el front door" at
the time — a leftover from earlier experimentation, then changed to "tv
control"): *"TV control is not available on this device."* Initially
hypothesized as a built-in-Alexa-domain-name collision (TV/entertainment
control). **This hypothesis is disproven by D below.**

**D.** Physical Echo Dot test #2 (invocation name reverted to
"computer control", full rebuild confirmed `SUCCEEDED` first): *"Computer
control isn't available on this Echo because the device doesn't support that
feature."* Different wording from C, same rejection class, but with a
completely different, non-domain-colliding invocation name — rules out the
name-collision theory from C.

**E.** `ask smapi simulate-skill` — the real SMAPI API, not the console UI —
called directly with `--input-content "open computer control"
--device-locale en-US`: returned `status: FAILED`,
`result.error.message: "An unexpected error occurred."` (opaque, no further
detail from the plain command; only `--full-response` short form was
captured, not the raw HTTP body/headers). Backend gunicorn log during this
window: **no new activity** — request never reached our endpoint via this
path either.

## The actual contradiction to explain
Skill status is all-green (build succeeded, manifest succeeded, enablement
confirmed `204`), yet **three of four** independent invocation attempts
(C, D, E) failed before ever reaching our endpoint, while the **one**
web-simulator attempt that did reach us (A) failed on missing
signature headers. That's two distinct failure classes across near-identical
conditions. Something is inconsistent in how Alexa's service routes to this
skill, or in what "green" status actually guarantees.

## Leading hypothesis (new, unverified) — Echo Dot is 1st generation
**Just learned mid-investigation: the physical test device is a 1st-generation
Echo Dot (released Nov 2016, long EOL'd by Amazon).** Not yet checked:
- Whether 1st-gen Echo Dot firmware supports Name-Free Interaction (NFI) /
  modern custom-skill invocation routing at all, or is frozen on old
  Alexa Voice Service firmware that predates current custom-skill invocation
  behavior.
- Amazon's official device support/EOL pages for whether 1st-gen Dot has
  reduced or discontinued skill-invocation support.
- Whether testing on the Alexa phone app or a newer/virtual device instead
  isolates the failure to this specific hardware.

This came up after C/D/E were already observed, so it wasn't controlled for.
Testing the same phrase from the Alexa Android app (a fully current client)
would help isolate "device firmware" vs. "account/skill routing" as the
cause — do this if easy.

## Other unverified hypotheses, roughly in priority order
1. **Account mismatch**: `get-skill-enablement-status` is scoped to the
   customerId tied to the CLI's OAuth token (the *developer* account used on
   hyperion via `ask configure`). If the Echo Dot is registered to a
   *different* Amazon account, it would never see this dev-stage skill —
   and Alexa's actual rejection wording for "skill not available to you"
   could plausibly render as C/D's messages. Not yet confirmed either way.
2. **"Skill testing enabled in: Development" console toggle** — a separate
   per-account UI switch on the Developer Console's Test tab, distinct from
   build status and from `get-skill-enablement-status`. Never explicitly
   checked whether this is ON. `get-skill-enablement-status` returning 204
   may or may not be the same gate as this toggle — unconfirmed.
3. Full raw response of `ask smapi simulate-skill --full-response` (headers +
   body) was never captured — might carry a requestId/trace useful for
   correlating against Alexa-side logs or forum reports of this exact error
   message.
4. Leftover placeholder manifest fields (`examplePhrases: "Alexa open hello
   world"`, `description: "Sample Full Description"`, `category:
   KNOWLEDGE_AND_TRIVIA`) — unlikely given build succeeded, but not ruled out
   as a runtime-only validation gate distinct from build-time validation.
5. The signature-verification failure from attempt A was never actually
   root-caused — only observed once. No code changes were made to fix it,
   only diagnostic `app.logger.info("Incoming headers: %s", ...)` added to
   `/opt/alexa-mqtt/app.py`'s `/alexa` route (still present, never triggered
   again since B/D/E never reached the backend at all).

## What to do
This needs actual research, not another blind retry:
- Look up whether "X isn't available on this Echo because the device doesn't
  support that feature" is a documented Alexa error string, and what triggers
  it (forums, Amazon docs, GitHub issues on ask-sdk repos).
- Look up 1st-gen Echo Dot + custom skill / NFI support status specifically.
- If possible, correlate via `ask smapi simulate-skill --full-response` (get
  the raw body, not the trimmed message) and any requestId it returns against
  Amazon's skill-testing troubleshooting docs.
- Check whether the Alexa Android app (mentioned earlier in this project by
  the user as another test surface) produces the *same* error or a different
  one — that result was never actually confirmed, only asked about.

Report back: is this a device-generation limitation (in which case the fix is
"test from a current-gen device/app instead"), an account-linking mismatch
(fix: same-account requirement), or something in our skill config that
build-time validation doesn't catch (fix: identify and correct the field).
