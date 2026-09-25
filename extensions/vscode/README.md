# Cortana for VS Code

A VS Code driver for **Cortana**, the local AI assistant. This is a
**reference scaffold** — source code you can read, build, and adapt.
It is **not published** to the VS Code Marketplace and has not been
packaged as a `.vsix`.

## What it does

- **`Cortana: Ask`** — prompts for a question, sends the active editor's
  language plus the current selection (or the whole file, capped at ~8k
  characters) as context to Cortana, and shows the reply in a side panel.
- **`Cortana: Complete With File Context`** — sends the same context and
  inserts Cortana's reply at the cursor.

Both commands call the Cortana API server (`core/apiserver.py` in the
cortana repo) over its OpenAI-compatible `POST /v1/chat/completions`
endpoint with a Bearer token. The server is **not** bundled and is **not**
auto-started — if it isn't reachable you get an honest error telling you
how to start it.

## Build

```bash
cd extensions/vscode
npm install
npm run compile
```

Then press **F5** in VS Code to launch an Extension Development Host with
the extension loaded.

## Pointing it at Cortana

1. Start the API server from the cortana repo:

   ```bash
   CORTANA_API_TOKEN=pick-a-secret python -m core.apiserver --port 18789
   ```

2. In VS Code settings (`settings.json` or the UI), set:
   - `cortana.apiUrl` → `http://127.0.0.1:18789` (the default)
   - `cortana.apiToken` → the same secret as the server's token

3. Run **Cortana: Ask** from the command palette.

## Honest notes

- Scaffold only: no tests, no telemetry, no Marketplace release. Treat it
  as a starting point for a real extension, not a finished product.
- Everything runs on localhost by default; the API server binds
  127.0.0.1 unless you explicitly pass `--bind-lan`.
- The token is a shared secret — keep it out of version control.
