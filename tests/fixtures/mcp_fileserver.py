#!/usr/bin/env python3
"""Real-world-style MCP filesystem server (test fixture).

Speaks MCP over newline-delimited JSON-RPC stdio, like the reference
filesystem servers do. Tools: list_dir, read_file, write_file, file_info.
All paths are confined to --root (or MCP_FS_ROOT); traversal is refused
with a JSON-RPC error. Only used by tests/test_mcp_fileserver.py.
"""
import json
import os
import sys

ROOT = os.path.abspath(sys.argv[sys.argv.index("--root") + 1]
                        if "--root" in sys.argv
                        else os.environ.get("MCP_FS_ROOT", os.getcwd()))


def _confine(path: str) -> str:
    target = os.path.abspath(os.path.join(ROOT, path or "."))
    if target != ROOT and not target.startswith(ROOT + os.sep):
        raise ValueError(f"path escapes root: {path!r}")
    return target


TOOLS = [
    {"name": "list_dir",
     "description": "List files in a directory relative to the server root.",
     "inputSchema": {"type": "object",
                     "properties": {"path": {"type": "string", "description": "relative dir"}},
                     "required": []}},
    {"name": "read_file",
     "description": "Read a UTF-8 text file relative to the server root.",
     "inputSchema": {"type": "object",
                     "properties": {"path": {"type": "string"}},
                     "required": ["path"]}},
    {"name": "write_file",
     "description": "Write text to a file relative to the server root (creates parents).",
     "inputSchema": {"type": "object",
                     "properties": {"path": {"type": "string"},
                                    "content": {"type": "string"}},
                     "required": ["path", "content"]}},
    {"name": "file_info",
     "description": "Size and mtime of a file relative to the server root.",
     "inputSchema": {"type": "object",
                     "properties": {"path": {"type": "string"}},
                     "required": ["path"]}},
]


def _text(t: str):
    return {"content": [{"type": "text", "text": t}]}


def _tool_error(t: str):
    d = _text(t)
    d["isError"] = True
    return d


def call_tool(name: str, args: dict):
    try:
        if name == "list_dir":
            target = _confine(args.get("path", "."))
            entries = sorted(os.listdir(target))
            return _text(json.dumps(entries))
        if name == "read_file":
            target = _confine(args["path"])
            with open(target, encoding="utf-8") as f:
                return _text(f.read())
        if name == "write_file":
            target = _confine(args["path"])
            os.makedirs(os.path.dirname(target) or ROOT, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(args.get("content", ""))
            return _text(f"wrote {len(args.get('content', ''))} chars to {args['path']}")
        if name == "file_info":
            target = _confine(args["path"])
            st = os.stat(target)
            return _text(json.dumps({"size": st.st_size, "mtime": st.st_mtime}))
        return _tool_error(f"unknown tool {name!r}")
    except (ValueError, OSError, KeyError) as e:
        return _tool_error(f"{type(e).__name__}: {e}")


def respond(msg_id, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": result}) + "\n")
    sys.stdout.flush()


def respond_error(msg_id, code, message):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg_id,
                                 "error": {"code": code, "message": message}}) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        method, msg_id = msg.get("method"), msg.get("id")
        if msg_id is None:
            continue  # notification (e.g. notifications/initialized)
        params = msg.get("params", {}) or {}
        if method == "initialize":
            respond(msg_id, {"protocolVersion": "2024-11-05",
                             "capabilities": {"tools": {}},
                             "serverInfo": {"name": "mcp-fileserver-fixture",
                                            "version": "1.0.0"}})
        elif method == "tools/list":
            respond(msg_id, {"tools": TOOLS})
        elif method == "tools/call":
            respond(msg_id, call_tool(params.get("name", ""),
                                      params.get("arguments", {}) or {}))
        elif method == "ping":
            respond(msg_id, {})
        else:
            respond_error(msg_id, -32601, f"unknown method {method!r}")


if __name__ == "__main__":
    main()
