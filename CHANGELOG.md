# Changelog — CORTANA

All notable changes, newest first. Dates are when the work landed on the
`audit/fix` branch. `JARVIS.md` (the user's own instructions file) is never
modified by any of this work.

## [server] — 2026-09-25 (branch `feature/server`, not yet merged)

**Reference cloud server** (`server/`): the honest minimal backend a
local-first assistant needs, so Microsoft (or anyone) can deploy it with
near-zero heavy lifting. Pure stdlib + `cryptography` (server-only;
`setup.py` now excludes `server/` from the CLI package).

- **Accounts**: email+password signup/login (PBKDF2-SHA256, 600k iters,
  per-user salt; argon2 upgrade path documented), session tokens (only
  SHA-256 stored), change-password, logout.
- **Social sign-in**: `POST /v1/auth/oidc/{google,apple,microsoft}` with
  real server-side ID-token validation (RS256 signature via JWKS,
  iss/aud/exp checks — unverifiable tokens are rejected, never trusted);
  GitHub via server-side code exchange + `/user` lookup (documented as
  non-OIDC). Exact client contract in `server/README.md` for the
  client-side auth round.
- **OAuth brokerage**: the server holds one OAuth app per provider
  (Google Drive, Gmail, Google Calendar, Outlook, GitHub); PKCE authorize
  flow, per-user tokens encrypted at rest (Fernet), refresh handled
  server-side — clients never see refresh tokens. Refuses to store tokens
  if the encryption key/package is missing instead of storing insecurely.
- **Device pairing**: short `CORT-XXXXXX` codes with explicit owner
  accept/reject; server is signaling-only and never sees conversation
  content (actual handoff stays device-to-device via `core/handoff.py`).
- **Hosted chat**: OpenAI-compatible `POST /v1/chat/completions`
  (incl. SSE streaming) relaying to a configured provider — the hosted
  counterpart to the on-device API; honest 501 when unconfigured.
- **One-command deploy**: `Dockerfile`, `docker-compose.yml` (app +
  postgres + redis provisioned for the production path), `.env.example`,
  Azure Container Apps bicep template, `server/README.md` 5-minute guide.
- **Honesty docs**: `server/PRODUCTION.md` — the exact hardening checklist
  (Postgres swap, Key Vault, Argon2, TLS, Redis rate limiting, audit
  logging, backups) with "deliberately out of scope" section.
- 27 new tests in `tests/test_server.py` (in-process server, no live
  network: stubbed JWKS/token/GitHub/chat upstreams). Rate limiting,
  security headers, secret-scrubbing log filter included.

## [rename] — 2026-09-25 (branch `rename/cortana`, not yet merged)

**Project rename: JARVIS → CORTANA.** Everything the user touches now says
Cortana: CLI (`cortana`, with a deprecated `jarvis` shim that prints a rename
notice and forwards), config dir `~/.cortana` (old `~/.jarvis` is copied, not
moved), config keys (`cortana_model`, `cortana_name`), keyring services
(`cortana-dev`, `cortana_cli`, `cortana_google_auth`), dashboard token header
`X-Cortana-Token`, installer (`~/.cortana-app`, `/usr/local/bin/cortana`),
Homebrew formula (`cortana.rb`), AUR package (`cortana`), PyPI distribution
(`cortana`). P2P wire actions and UDP discovery bytes are unchanged so older
nodes stay interoperable. A few tasteful easter eggs: a `/clippy` command, a
Halo-flavored boot line, and a classic-Windows sign-off on `/exit`.

New dev toggle: **auto-approve**. `cortana --yes` / `-y`,
`CORTANA_AUTO_APPROVE=1`, or `"auto_approve": true` in config answers routine
confirmation prompts yes automatically (never on by default). Startup warns
clearly, every auto-approved action is logged to
`~/.cortana/logs/auto_approve.log` (0600), credential/trust prompts still ask,
and the sandbox is unaffected. Migration notes: `~/.jarvis` is copied to
`~/.cortana` (old dir left untouched, also when only cache dirs exist);
`get_env_with_config("cortana_*")` honors legacy `JARVIS_*` env spellings.


All notable changes, newest first. Dates are when the work landed on the
`audit/fix` branch. `JARVIS.md` (the user's own instructions file) is never
modified by any of this work.

## [0.2.6] — 2026-09-25 (release candidate, not yet tagged)

The scheduler/dashboard release — the end of the audit arc. Every item below
was re-verified with `compileall` clean and the full test suite green.

### New: task scheduler (`/schedule`)

- Persistent in-process scheduler: one-shot (`--at`), interval (`--every`),
  and cron jobs (`--cron "0 4 * * *"`).
- Jobs stored in `~/.cortana/scheduler_jobs.json` (atomic writes, mode
  `0600`); append-only run history in `~/.cortana/scheduler_runs.jsonl`.
- Whitelisted actions only: `/brief`, `/ollama auto-pull`, `/research`,
  `/health`, and `shell: …` executed **exclusively** through the sandbox —
  anything else is rejected.
- Missed runs are logged honestly; missed one-shot jobs are disabled rather
  than silently discarded. Starts with the normal interactive session.
- `/ollama auto-pull` help now points at `/schedule` instead of system cron.

### New: local web dashboard (`/dashboard`, `cortana dashboard`)

- Stdlib-only `http.server` UI replacing the old Rich terminal dashboard.
- Binds loopback (`127.0.0.1`) by default; `--lan` binds all interfaces with
  an explicit warning.
- Per-instance random token at `~/.cortana/dashboard_token` (`0600`), sent as
  `?token=` or `X-Cortana-Token`, compared with `hmac.compare_digest`.
- Live panels read real state: providers, P2P peers, Ollama hosts/models,
  scheduler jobs + recent runs, brief watcher, redacted log tail.
- Chat calls `core.brain.think`; a read-only command whitelist
  (`/health`, `/models`, `/schedule list`, `/schedule log`, `/ollama ps`,
  `/ollama stats`, `/brief status`, `/p2p-status`) — nothing else executes.
- Log rendering redacts credential/token-shaped material before display.

### Hardening

- **Startup ≈12× faster** (`import cli`: ~5.0s → ~0.43s): LiteLLM and Paramiko
  now import lazily on first real use, with regression tests that forbid
  preloading.
- **Actionable errors**: Ollama unreachable → "start it with `ollama serve`";
  model not pulled → "`/ollama pull <model>`"; missing provider key →
  "run `/connect`"; dashboard port in use → "try `--port 0`". One line each,
  no tracebacks in normal mode.
- **P2P capability flags**: peers advertise `local_services.scheduler` and
  `local_services.dashboard` separately from P2P action compatibility, so
  no peer falsely claims scheduler/dashboard as callable P2P actions.
- Realistic filesystem MCP fixture (`tests/fixtures/mcp_fileserver.py`)
  speaking real MCP-style JSON-RPC over stdio (tools/list, tools/call,
  root-confined file tools).
- `/menu` updated for all new commands.

### Docs

- README: new "What's New in v0.2.6", feature sections for every new
  subsystem, and a full command reference table.
- This changelog.

## 0.1.7 → 0.2.6 audit arc (2026-09-25, branch `audit/fix`)

Everything between the last packaged release and 0.2.6, in landing order:

1. **Easy-connect**: provider linking wizard, secure key storage (keyring →
   config fallback), `is_configured()` single definition, `/connections`
   status tables, verified per-provider key-page URLs.
2. **Capability round**: deterministic P2P loopback tests (plaintext + TLS),
   real per-provider validation endpoints, opt-in Linux code sandbox
   (`tools/sandbox.py`: resource limits + bubblewrap isolation), honest
   browser backend probing (`tools/browser.py` never claims JS rendering).
3. **Packaging**: idempotent one-line `install.sh` (Linux/macOS), Homebrew
   formula (v0.1.7 tarball, verified sha256), PyPI wheel/sdist, `PACKAGING.md`
   runbook, AUR skeleton. Nothing published yet.
4. **Hive mind / swarm / MCP / research**: `/hive` consensus across
   providers (failures skipped, never faked), `/swarm` planner→workers→
   reviewer (sandboxed code workers), stdlib-only MCP client, cited
   multi-query `/research` with citation validation.
5. **Ollama fleet / edge round**: `/ollama ps/pull/prune/bench/stats`,
   multi-host pools, `/thin` thin client, `/rewind`/`/branch`/`/branches`/
   `/diff` time-travel, verified `/skill` sharing, `/brief` watcher,
   `/handoff` session transfer.

## [0.1.7] — last packaged release

The final state before the audit: multi-LLM support, Gemini-style slash
commands, personality profiles, memory management, installer script, and the
Homebrew formula + AUR skeleton now kept at this version until 0.2.6 is
tagged.
