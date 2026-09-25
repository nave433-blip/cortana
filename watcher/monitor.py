import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from core.brain import think
from memory.vector import add

# Directories that should never trigger analysis (VCS metadata, caches,
# virtualenvs). Matching is done per path component.
IGNORE_DIRS = {
    ".git", "__pycache__", ".venv", "venv", ".audit-venv",
    "node_modules", ".mypy_cache", ".pytest_cache",
}

# Minimum seconds between analyses of the same file. Editors often emit
# several modified events per save; without this every save would fire
# multiple LLM calls.
DEBOUNCE_SECONDS = 3.0

_last_seen = {}


def _ignored(path: str) -> bool:
    parts = path.replace("\\", "/").split("/")
    return any(p in IGNORE_DIRS for p in parts)


class Handler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory:
            return
        src = event.src_path
        if not src.endswith(".py") or _ignored(src):
            return
        now = time.time()
        if now - _last_seen.get(src, 0) < DEBOUNCE_SECONDS:
            return
        _last_seen[src] = now
        try:
            with open(src) as f:
                code = f.read()

            print(f"\n[WATCHER] Analyzing {src}...")
            # think() returns the analysis text (str).
            analysis = think(code, "analyze changes")
            analysis = analysis if isinstance(analysis, str) else str(analysis)
            print("Analysis complete.")

            # Store analysis in memory
            if not add(f"File: {src} | Analysis: {analysis[:500]}"):
                print("[WATCHER] memory store unavailable (embeddings offline?); analysis not saved")
        except Exception as e:
            print(f"Error analyzing {src}: {e}")


def start_monitor(path="."):
    observer = Observer()
    observer.schedule(Handler(), path, recursive=True)
    observer.start()
    print(f"Watcher started. Monitoring {path} for changes...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    start_monitor()
