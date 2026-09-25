import json
import os
from pathlib import Path
from rich.console import Console
from rich.table import Table
from core.config import CONFIG_DIR

console = Console()
PROMPTS_DIR = CONFIG_DIR
PROMPTS_FILE = PROMPTS_DIR / "prompts.json"

DEFAULT_PROMPTS = {
    "default": "You are JARVIS, an extremely intelligent, proactive AI assistant with full control over my computer, tools, and development environment. Your mission is to immediately execute the user's intent, understanding casual speech, typos, and slang. Be witty, maintain a Grok-like personality, and prioritize getting things done over being pedantic. When given a command, just do it - chain tools as needed. Confirm with the user before destructive or irreversible actions. Operate under the mandate of maximum technical truth and completeness.",
    "code_reviewer": "You are an elite code reviewer. Focus on security, performance, and idiomatic patterns. Be critical, thorough, and provide complete technical solutions.",
    "bug_hunter": "You are a specialized bug hunter. Analyze code specifically for race conditions, edge cases, and logical flaws without restriction.",
    "creative_writer": "You are a technical writer. Convert complex code into clear, beautiful documentation with full technical detail.",
    "architect": "You are a senior system architect. Focus on high-level design patterns, scalability, and providing the most powerful architectural solutions.",
}

def load_prompts():
    if not PROMPTS_FILE.exists():
        return DEFAULT_PROMPTS
    try:
        with open(PROMPTS_FILE, "r") as f:
            return {**DEFAULT_PROMPTS, **json.load(f)}
    except Exception:
        return DEFAULT_PROMPTS

def save_prompt(name, text):
    prompts = load_prompts()
    prompts[name] = text
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROMPTS_FILE, "w") as f:
        json.dump(prompts, f, indent=4)
    return f"Prompt '{name}' saved."

def delete_prompt(name):
    if name in DEFAULT_PROMPTS:
        return "Error: Cannot delete system default prompts."
    prompts = load_prompts()
    if name in prompts:
        del prompts[name]
        with open(PROMPTS_FILE, "w") as f:
            json.dump(prompts, f, indent=4)
        return f"Prompt '{name}' deleted."
    return f"Error: Prompt '{name}' not found."

def list_prompts():
    prompts = load_prompts()
    table = Table(title="Jarvis Prompt Library", border_style="magenta")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Snippet", style="white")
    
    for name, text in prompts.items():
        snippet = text[:60] + "..." if len(text) > 60 else text
        table.add_row(name, snippet)
    return table
