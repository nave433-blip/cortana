/* Cortana for VS Code — reference scaffold (NOT published to the Marketplace).
 *
 * Two commands:
 *   - cortana.ask                — ask Cortana about the current file/selection,
 *                                  reply shown in a webview panel.
 *   - cortana.completeWithContext — send the file (capped) to Cortana and insert
 *                                  the reply at the cursor.
 *
 * Both commands talk to the Cortana API server (core/apiserver.py) over its
 * OpenAI-compatible POST /v1/chat/completions endpoint with a Bearer token.
 * The server is NOT bundled or auto-started: it must already be running on
 * localhost. Errors say so plainly instead of inventing answers.
 */

import * as vscode from "vscode";

const MAX_CONTEXT_CHARS = 8000; // cap file context sent to the server

interface ChatMessage {
  role: string;
  content: string;
}

function getConfig(): { apiUrl: string; apiToken: string } {
  const cfg = vscode.workspace.getConfiguration("cortana");
  const apiUrl = (cfg.get<string>("apiUrl") || "http://127.0.0.1:18789").replace(
    /\/+$/,
    ""
  );
  const apiToken = cfg.get<string>("apiToken") || "";
  return { apiUrl, apiToken };
}

/** Build the chat payload from the active editor: language + selection/file. */
function buildMessages(instruction: string): ChatMessage[] | null {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showWarningMessage(
      "Cortana: no active editor — open a file first."
    );
    return null;
  }
  const doc = editor.document;
  const selection = editor.selection;
  const selected =
    selection && !selection.isEmpty
      ? doc.getText(selection)
      : doc.getText();
  const context = selected.slice(0, MAX_CONTEXT_CHARS);
  const truncated =
    selected.length > MAX_CONTEXT_CHARS ? "\n[... context truncated ...]" : "";
  return [
    {
      role: "system",
      content:
        "You are Cortana, a local AI coding assistant. Answer concisely. " +
        "When asked to complete code, return only the code to insert, no prose.",
    },
    {
      role: "user",
      content:
        `${instruction}\n\nFile language: ${doc.languageId}\n` +
        `File: ${doc.fileName}\n\nContext:\n${context}${truncated}`,
    },
  ];
}

async function callCortana(messages: ChatMessage[]): Promise<string> {
  const { apiUrl, apiToken } = getConfig();
  if (!apiToken) {
    throw new Error(
      "Cortana: no API token set. Set cortana.apiToken in settings " +
        "(same value as the server's CORTANA_API_TOKEN env var or " +
        "~/.cortana/api_token)."
    );
  }
  let resp: Response;
  try {
    resp = await fetch(`${apiUrl}/v1/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiToken}`,
      },
      body: JSON.stringify({ model: "cortana-default", messages }),
    });
  } catch (e) {
    throw new Error(
      "Cortana: cannot reach the API server at " +
        `${apiUrl}. Start it first (e.g. CORTANA_API_TOKEN=... ` +
        `python -m core.apiserver --port 18789 from the cortana repo). ` +
        `Details: ${String(e)}`
    );
  }
  if (!resp.ok) {
    const body = await resp.text().catch(() => "");
    throw new Error(
      `Cortana: API server returned HTTP ${resp.status}. ${body.slice(0, 200)}`
    );
  }
  const data = (await resp.json()) as {
    choices?: { message?: { content?: string } }[];
    error?: { message?: string };
  };
  if (data.error) {
    throw new Error(`Cortana: ${data.error.message || "unknown API error"}`);
  }
  const content = data.choices?.[0]?.message?.content;
  if (!content) {
    throw new Error("Cortana: empty reply from the API server.");
  }
  return content;
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" } as Record<string, string>)[c]
  );
}

function showAnswerPanel(question: string, answer: string): void {
  const panel = vscode.window.createWebviewPanel(
    "cortanaAnswer",
    "Cortana answer",
    vscode.ViewColumn.Beside,
    {}
  );
  panel.webview.html = `<!DOCTYPE html><html><head><meta charset="utf-8">
<style>body{font-family:system-ui,sans-serif;padding:12px;line-height:1.5}
pre{background:#1e1e1e;padding:10px;border-radius:6px;overflow:auto}</style>
</head><body><h3>Cortana</h3><p><i>${escapeHtml(question)}</i></p>
<hr><pre>${escapeHtml(answer)}</pre></body></html>`;
}

async function askCommand(): Promise<void> {
  const question = await vscode.window.showInputBox({
    prompt: "Ask Cortana (current file/selection is sent as context)",
    placeHolder: "e.g. explain this function",
  });
  if (!question) {
    return;
  }
  const messages = buildMessages(question);
  if (!messages) {
    return;
  }
  await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Notification, title: "Cortana is thinking…" },
    async () => {
      try {
        const answer = await callCortana(messages);
        showAnswerPanel(question, answer);
      } catch (e) {
        vscode.window.showErrorMessage(String(e instanceof Error ? e.message : e));
      }
    }
  );
}

async function completeCommand(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showWarningMessage("Cortana: no active editor.");
    return;
  }
  const messages = buildMessages(
    "Complete the code where the cursor context ends. Return ONLY the completion text."
  );
  if (!messages) {
    return;
  }
  await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Notification, title: "Cortana is completing…" },
    async () => {
      try {
        const completion = await callCortana(messages);
        await editor.edit((edit) => {
          editor.selections.forEach((sel) => edit.insert(sel.active, completion));
        });
      } catch (e) {
        vscode.window.showErrorMessage(String(e instanceof Error ? e.message : e));
      }
    }
  );
}

export function activate(context: vscode.ExtensionContext): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("cortana.ask", askCommand),
    vscode.commands.registerCommand("cortana.completeWithContext", completeCommand)
  );
}

export function deactivate(): void {
  // nothing to tear down
}
