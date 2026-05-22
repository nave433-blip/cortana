import os
import json
import datetime
import traceback
import tempfile
from rich.console import Console
from rich.panel import Panel

console = Console()

LOG_DIR = os.path.expanduser("~/.jarvis/logs")

class ErrorLogger:
    @staticmethod
    def log_error(error, context="General"):
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            log_file = os.path.join(LOG_DIR, f"error_{datetime.date.today().isoformat()}.log")
        except OSError:
            log_file = os.path.join(tempfile.gettempdir(), f"jarvis_error_{datetime.date.today().isoformat()}.log")
        
        timestamp = datetime.datetime.now().isoformat()
        stack_trace = traceback.format_exc()
        
        log_entry = {
            "timestamp": timestamp,
            "context": context,
            "error": str(error),
            "stack_trace": stack_trace
        }
        
        try:
            with open(log_file, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        except OSError:
            pass
            
        return log_entry

    @staticmethod
    def auto_debug(error_msg):
        """Autonomous analysis of an error message."""
        from core.brain import think
        prompt = f"Analyze this error and suggest a fix:\n{error_msg}"
        res = think("System Debugger", prompt)
        suggestion = res.get("text", str(res)) if isinstance(res, dict) else str(res)
        console.print(Panel(suggestion, title="🧠 JARVIS Auto-Debug Suggestion", border_style="yellow"))
        return suggestion
