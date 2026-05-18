import os
import subprocess
import webbrowser
from rich.console import Console

console = Console()

def open_url(url: str, *args, **kwargs):
    """
    Opens a URL in the browser. 
    On Linux, attempts to use Chrome specifically if available, 
    otherwise falls back to the default webbrowser module.
    """
    try:
        if os.name == 'posix': # Linux / macOS
            # Check for common chrome commands on Linux
            chrome_commands = ["google-chrome", "google-chrome-stable", "google-chrome-beta", "chromium", "chromium-browser"]
            for cmd in chrome_commands:
                try:
                    # Check if command exists without opening browser yet
                    if subprocess.run(["which", cmd], capture_output=True).returncode == 0:
                        subprocess.Popen([cmd, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        return True
                except:
                    continue
        
        # Fallback to default behavior
        webbrowser.open(url, *args, **kwargs)
        return True
    except Exception as e:
        console.print(f"[dim]Note: Failed to open browser automatically: {e}[/dim]")
        return False
