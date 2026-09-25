# Cortana Adoption Guide

How to integrate Cortana — a local-first AI assistant — into your own
products, editors, and infrastructure. Everything described here uses only
public interfaces (OpenAI-compatible REST, documented extension APIs).
No reverse-engineering, no proprietary protocols.

## Architecture

```
                    +----------------------+
                    |        CLI           |  (cli.py — Typer + Rich,
                    |  (interactive chat)  |   interactive prompts)
                    +----------+-----------+
                               |
                    +----------v-----------+
                    |     cortana_core     |  (stable Python library:
                    |  think / think_structured   no CLI, no UI,
                    |  hive_ask / load_config    lazy imports)
                    +----+-----+-----+-----+
                         |     |     |     |
            +------------v+ +---v--+ +-v---+ +-----v-----+
            |  Providers  | | Hive | |Sandbox| |  P2P    |
            | (Ollama,    | |(multi| |(Linux | | (LAN    |
            |  OpenAI,    | |model | |bwrap/ | | peer   |
            |  Gemini…)   | |con-  | |sub-  | | disc-  |
            +-------------+ |sensus)| |proc) | | overy) |
                            +------+ +------+ +---------+
                                              |
                    +-------------------------+-------------------------+
                    |                                                   |
        +-----------v-----------+                        +--------------v--------+
        |  API server           |                        |  VS Code driver       |
        |  (core/apiserver.py)  |  <---- HTTP/JSON ---->  |  (extensions/vscode)  |
        |  OpenAI-compatible    |                        |  cortana.ask /        |
        |  /v1/chat/completions |                        |  cortana.completeWith |
        |  /v1/models           |                        |  Context (scaffold)   |
        +-----------------------+                        +-----------------------+
```

- **`cortana_core`** is the embedding surface: import it, call `think()`,
  and you have Cortana's brain with zero CLI baggage.
- **`core/apiserver.py`** is the network surface: stdlib-only HTTP server
  speaking the OpenAI chat-completions dialect.
- **`extensions/vscode/`** is the editor surface: a reference scaffold that
  drives the API server from VS Code.
- Providers, the sandbox, and P2P are interchangeable backends behind
  `cortana_core` — integrators never touch them directly.

## Copilot → Cortana feature map

| Copilot capability | Cortana equivalent | Notes |
|---|---|---|
| Inline completions | `cortana.completeWithContext` (VS Code scaffold) + `POST /v1/chat/completions` | Works, but no ghost-text streaming UI — scaffold inserts the reply at the cursor |
| Chat sidebar | `cortana.ask` (VS Code scaffold) → webview panel | Basic: question + file context in, answer out |
| Agent mode (multi-step edits) | `cortana_core.hive_ask` + `run_sandboxed` | Building blocks exist; no autonomous file-editing loop is wired up for you |
| PR assistance / code review | Not built in | Honest gap — you would compose this from `think_structured` + your own diff tooling |
| Model choice | `GET /v1/models` lists configured providers | You bring the provider keys; Cortana routes |
| Enterprise SSO / org policy | ❌ Missing | No SSO, no org-level policy engine |
| Telemetry / usage analytics | ❌ Missing by design | Cortana keeps nothing; `usage` fields in API responses are zeros |
| Offline / local models | ✅ Native | Ollama, llama.cpp, vLLM, GPT4All are first-class providers |
| Streaming responses | ❌ Not supported | `stream: true` returns HTTP 400 — polling or full responses only |

## Integration points

### 1. OpenAI-compatible API

Start the server (loopback-only by default):

```bash
CORTANA_API_TOKEN=pick-a-secret python -m core.apiserver --port 18789
```

List models:

```bash
curl -s http://127.0.0.1:18789/v1/models \
  -H "Authorization: Bearer pick-a-secret"
```

Chat:

```bash
curl -s http://127.0.0.1:18789/v1/chat/completions \
  -H "Authorization: Bearer pick-a-secret" \
  -H "Content-Type: application/json" \
  -d '{"model": "cortana-default",
       "messages": [{"role": "user", "content": "Explain recursion in one paragraph."}]}'
```

Response is the standard OpenAI shape (`choices[0].message.content`).
`stream: true` → HTTP 400. Bad auth → HTTP 401. Brain failure → HTTP 502.
The `model` you pass is echoed back; Cortana maps it to a configured
provider when it recognizes the id, otherwise it uses the default model.

### 2. Embedding `cortana_core` in Python

```python
import cortana_core

# One-shot answer
reply = cortana_core.think("code-review", "Is this function pure? ...")

# Structured result: {"ok", "text", "provider", "error"?}
res = cortana_core.think_structured("summarize", long_text)
if res["ok"]:
    print(res["text"], "— via", res["provider"])

# Multi-provider consensus
verdict = cortana_core.hive_ask("Which sorting algorithm here and why?")

# Sandboxed shell (Linux: bubblewrap when available)
out = cortana_core.run_sandboxed("pytest -q", timeout=120)

# Config + approvals
cfg = cortana_core.load_config()
if cortana_core.confirm("Deploy to staging?", sensitive=True):
    ...
```

### 3. VS Code driver

`extensions/vscode/` is a reference scaffold (not published): two commands
(`cortana.ask`, `cortana.completeWithContext`), settings `cortana.apiUrl`
(default `http://127.0.0.1:18789`) and `cortana.apiToken`. Build with
`npm install && npm run compile`, then F5. See its README for details.

### 4. P2P protocol note

Cortana instances discover each other on the LAN (`core/p2p.py`):
loopback/LAN HTTP with an optional TLS mode, peer permission lists, and
path-confined file serving. It is a coordination channel, not an inference
API — **provider API keys are never transmitted over P2P**. If you build on
it, keep that invariant: only names/statuses cross the wire, never secrets.

### 5. MCP client note

`core/mcp_client.py` is a stdlib-only MCP (Model Context Protocol) client
over stdio JSON-RPC: it performs the initialize handshake, lists tools,
and calls them — with a confirmation gate for untrusted servers. Servers
are declared in `~/.cortana/config.json` under `"mcp_servers"`. If you
integrate Cortana as an MCP *host*, this is the module to wrap; if you want
Cortana *as* an MCP server, put the OpenAI-compatible API server behind
your own MCP stdio shim — the JSON shapes are one small translation apart.

## Proprietary drop-in slots

Some capabilities can only ship as licensed components (model weights,
wake-word detectors). Cortana reserves clearly-marked slots for them so a
licensee can drop a file in without touching core code:

```
proprietary/                # not in the repo — created by the licensee
├── wake_word.onnx          # wake-word detection model
├── voice_model.bin         # speech-to-text / text-to-speech weights
└── manifest.json           # {"wake_word": "wake_word.onnx", ...}
```

**Contract:** drop the file(s) into `proprietary/`, then set one config
key naming the component (e.g. `"wake_word_model": "proprietary/wake_word.onnx"`).
Core code checks for the file's presence at runtime; when it is absent the
feature reports "not available" instead of failing or faking it.

> **Note:** the voice subsystem itself lands in a later round. The slots
> above describe the intended contract; today `voice/` contains only the
> local (non-proprietary) voice scaffolding. Do not treat the
> `proprietary/` directory as existing yet.

Current reserved slots:

| Slot | Config key | Behavior when empty |
|---|---|---|
| Wake-word model | `wake_word_model` | Wake-word listening reports unavailable |
| Voice (STT/TTS) weights | `voice_model` | Voice I/O reports unavailable, text path unaffected |

## Security notes for integrators

- **Loopback by default.** The API server and dashboard bind 127.0.0.1.
  `--bind-lan` / `bind_lan=True` binds 0.0.0.0 only with an explicit flag
  and prints a loud warning. Never bind LAN in production without TLS and
  a strong token in front of it.
- **Token auth.** Every API request needs `Authorization: Bearer <token>`.
  The token comes from `CORTANA_API_TOKEN` or is generated per run and
  stored 0600 at `~/.cortana/api_token`. Tokens are never logged.
- **No keys over P2P.** Provider API keys live in the OS keyring (or a
  0600 fallback file) and are never serialized onto the network —
  not to peers, not to the dashboard, not to editor plugins. The
  `/v1/models` endpoint exposes model *names* only.
- **Sandboxing.** `run_sandboxed` runs shell commands under Linux
  namespaces via bubblewrap when available (resource limits, no network by
  default), falling back to a plain subprocess elsewhere. Treat sandbox
  output as untrusted data, not as instructions.
- **Approvals.** Destructive or credential-touching actions go through
  `core.approvals.confirm`; `sensitive=True` always asks the human even
  in auto-approve mode. Integrators embedding `cortana_core` inherit this
  gate — do not bypass it.
