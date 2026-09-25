# JARVIS: The Ultimate Proactive AI Assistant (v0.2.6)

JARVIS is a proactive AI engineering assistant that runs locally on macOS and Linux. It combines high-speed technical reasoning with deep system control and multi-model aggregator capabilities.

## 🚀 What's New in v0.2.6
- **Sovereign Reinstall:** New `/reinstall` command for a clean system refresh.
- **Ollama Auto-Connect:** JARVIS autonomously detects and launches the Ollama application on startup.
- **Reasoning Fix:** Optimized LLM communication to eliminate hangs and provide faster response feedback.
- **Proactive Account Center:** Intelligently handles "log in" and "link account" requests.
- **High-Fidelity Menu:** Redesigned `/menu` dashboard with categorized tool groups.

## 💎 Core Features
- **Multi-Model Aggregator:** Switch between **Ollama**, **OpenAI**, **Anthropic**, **Gemini**, **Mistral**, **DeepSeek**, **Groq**, and more.
- **Gemini-Style Interface:** Transparent reasoning blocks and Warp-inspired command input.
- **AI Tool Hub:** Native launchers for **Claude Code**, **Copilot CLI**, and **Hermes**.
- **Vector Memory:** Semantic context storage using FAISS and local embeddings.

## 📦 Installation
```bash
# macOS
brew install --cask https://raw.githubusercontent.com/nave433-blip/jarvis-term/master/jarvis-term.rb
# OR (macOS and Linux)
pip install git+https://github.com/nave433-blip/jarvis-dev.git
```

On Linux, system packages install via your native package manager (apt, dnf, pacman, or zypper) when available.

## 🔌 Connecting your AI providers

Run the interactive setup wizard any time:

- `/connect` (interactive chat) or `connect-provider <name> [--host URL] [--key KEY]` (CLI)
- `/connections` (interactive chat) or `connections [--test]` (CLI) — status table for all 18 providers

The wizard lists every supported provider with a status dot (● configured / ○ not),
auto-detects a running **Ollama** (`GET http://localhost:11434/api/tags`, one-confirm setup,
opt-in auto-repair), and accepts a custom host for the other local providers
(vLLM, SGLang, GPT4All, llama.cpp, NVIDIA NeMo, Local server). For API-key providers
it shows the provider's key page URL and reads the key with hidden input.

Key storage: keys are validated **before** they are saved and live in the OS
keyring (service `jarvis-dev`, account `jarvis-<provider>`). If no keyring backend
is available, JARVIS falls back to `~/.jarvis/keys.json` with `0600` permissions and
prints a clear warning that this is less secure. Keys are never printed, logged, or
echoed — the status table only shows set/not-set. Keys left in the old config-file
store are migrated into the keyring on first successful connect and removed from
the config file.

## 👨‍💻 Created By
**Nave433 (Evan Shipley)**
