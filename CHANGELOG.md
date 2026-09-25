# Changelog — CORTANA

All notable changes, newest first. Dates are when the work landed on the
`audit/fix` branch. `JARVIS.md` (the user's own instructions file) is never
modified by any of this work.

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
