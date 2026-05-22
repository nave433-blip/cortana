"""
Unit tests for the intent parser integration examples.

- Simulates an LLM client by returning exact assistant JSON strings.
- Validates the returned JSON against the schema (including optional 'ui').
- Asserts parse_with_model returns the parsed object for valid responses,
  and returns the noop fallback for invalid/malformed responses.
Run with: pytest -q
Requires: pytest, jsonschema
"""
import json
import jsonschema
import pytest
from typing import Any, Dict

SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["internal", "shell", "help", "noop"]},
        "target": {"type": "string"},
        "args": {"type": "array", "items": {"type": "string"}},
        "confirm": {"type": "boolean"},
        "ui": {
            "type": ["object", "null"],
            "properties": {
                "title": {"type": "string"},
                "subtitle": {"type": "string"},
                "markdown": {"type": "string"},
                "buttons": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "action": {"type": "string", "enum": ["confirm", "cancel", "help", "run", "open"]},
                            "primary": {"type": "boolean"},
                        },
                        "required": ["label", "action"],
                        "additionalProperties": False,
                    },
                },
            },
            "additionalProperties": False,
        },
    },
    "required": ["type", "target", "args", "confirm"],
    "additionalProperties": False,
}

NOOP = {"type": "noop", "target": "", "args": [], "confirm": False, "ui": None}


def validate(obj: Any) -> bool:
    try:
        jsonschema.validate(obj, SCHEMA)
        return True
    except Exception:
        return False


class FakeClient:
    def __init__(self, assistant_text: str):
        # assistant_text: the raw assistant response (should be JSON string)
        self.assistant_text = assistant_text

    def chat(self, messages, temperature, top_p, max_tokens):
        # Mirror the simple client.chat API used in examples
        return self.assistant_text


def parse_with_model(client: Any, user_text: str, system_prompt: str) -> Dict[str, Any]:
    """
    Minimal parse_with_model used in tests: call client.chat, parse JSON,
    validate against SCHEMA and return parsed object or NOOP fallback.
    """
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}]
    # deterministic settings
    resp_text = client.chat(messages=messages, temperature=0, top_p=1, max_tokens=300)
    try:
        parsed = json.loads(resp_text)
    except Exception:
        return NOOP
    if not validate(parsed):
        return NOOP
    # ensure ui present if missing for consistent test objects
    if "ui" not in parsed:
        parsed["ui"] = None
    return parsed


# Minimal system prompt placeholder used by parse_with_model in tests
SYSTEM_PROMPT = "SYSTEM PROMPT (trimmed for tests)"


# Examples from your prompt (exact expected JSON objects)
EXAMPLES = [
    (
        'scan /etd drive  for useful code to use in n4v3r41n program',
        {
            "type": "internal",
            "target": "scan",
            "args": ["/etd", "n4v3r41n"],
            "confirm": False,
            "ui": {
                "title": "Scan /etd for code",
                "subtitle": "Suggested search for n4v3r41n",
                "markdown": "Found likely candidates: repository files, scripts.",
                "buttons": [
                    {"label": "Run scan", "action": "run", "primary": True},
                    {"label": "Show help", "action": "help", "primary": False},
                ],
            },
        },
    ),
    (
        "add features to understand any command make it work like rival cli's",
        {
            "type": "internal",
            "target": "add-feature",
            "args": ["understand any command", "rival cli style"],
            "confirm": False,
            "ui": {
                "title": "Queue feature",
                "subtitle": "Add feature: natural language command parsing",
                "markdown": "Will create a TODO/issue for the dev queue.",
                "buttons": [
                    {"label": "Confirm add", "action": "confirm", "primary": True},
                    {"label": "Cancel", "action": "cancel", "primary": False},
                ],
            },
        },
    ),
    (
        "run git status",
        {
            "type": "shell",
            "target": "git status",
            "args": [],
            "confirm": False,
            "ui": {
                "title": "Run git status",
                "subtitle": "Read-only git status",
                "buttons": [
                    {"label": "Run", "action": "run", "primary": True},
                    {"label": "Cancel", "action": "cancel", "primary": False},
                ],
            },
        },
    ),
    (
        "delete all .pyc files under /usr/local/lib",
        {
            "type": "shell",
            "target": 'find /usr/local/lib -name "*.pyc" -delete',
            "args": [],
            "confirm": True,
            "ui": {
                "title": "Delete .pyc files",
                "subtitle": "This will permanently delete files under /usr/local/lib",
                "markdown": 'find /usr/local/lib -name "*.pyc" -delete',
                "buttons": [
                    {"label": "Delete (requires confirmation)", "action": "confirm", "primary": True},
                    {"label": "Cancel", "action": "cancel", "primary": False},
                ],
            },
        },
    ),
    (
        "what can you do?",
        {
            "type": "help",
            "target": "",
            "args": [],
            "confirm": False,
            "ui": {
                "title": "Help: commands",
                "subtitle": "List available commands",
                "markdown": "Try: `scan /path`, `add-feature ...`, `run git status`",
                "buttons": [{"label": "Show commands", "action": "help", "primary": True}],
            },
        },
    ),
    (
        "",  # empty input
        {"type": "noop", "target": "", "args": [], "confirm": False, "ui": None},
    ),
]


@pytest.mark.parametrize("user_text, expected", EXAMPLES)
def test_examples_return_parsed_object(user_text, expected):
    # simulate model returning the exact expected JSON string
    client = FakeClient(json.dumps(expected))
    parsed = parse_with_model(client, user_text, SYSTEM_PROMPT)
    assert parsed == expected


def test_malformed_json_returns_noop():
    client = FakeClient("this is not json")
    parsed = parse_with_model(client, "run something", SYSTEM_PROMPT)
    assert parsed == NOOP


def test_invalid_schema_returns_noop():
    # model returns JSON missing required fields (e.g., missing 'confirm')
    bad = {"type": "shell", "target": "ls -la", "args": []}  # confirm missing
    client = FakeClient(json.dumps(bad))
    parsed = parse_with_model(client, "ls -la", SYSTEM_PROMPT)
    assert parsed == NOOP


def test_ui_optional_handling():
    # model returns valid object without ui — parse_with_model should add ui: None
    obj = {"type": "shell", "target": "git status", "args": [], "confirm": False}
    client = FakeClient(json.dumps(obj))
    parsed = parse_with_model(client, "git status", SYSTEM_PROMPT)
    assert parsed["ui"] is None
    # base fields remain
    assert parsed["type"] == "shell"
    assert parsed["target"] == "git status"
