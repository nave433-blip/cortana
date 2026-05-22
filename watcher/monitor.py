import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from core.brain import think
from memory.vector import add

class Handler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(".py"):
            try:
                with open(event.src_path) as f:
                    code = f.read()

                print(f"\n[WATCHER] Analyzing {event.src_path}...")
                res = think(code, "analyze changes")
                analysis = res.get("text", str(res)) if isinstance(res, dict) else str(res)
                print("Analysis complete.")
                
                # Store analysis in memory
                add(f"File: {event.src_path} | Analysis: {analysis[:500]}")
            except Exception as e:
                print(f"Error analyzing {event.src_path}: {e}")

def start_monitor():
    observer = Observer()
    observer.schedule(Handler(), ".", recursive=True)
    observer.start()
    print("Watcher started. Monitoring for changes...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    start_monitor()
