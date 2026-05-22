import subprocess
import glob as python_glob
import os

def grep(pattern, path="."):
    try:
        # Simple grep-like search
        results = []
        for root, dirs, files in os.walk(path):
            if ".git" in root or "venv" in root: continue
            for file in files:
                if file.endswith(('.py', '.md', '.txt', '.cfg', '.toml')):
                    full_path = os.path.join(root, file)
                    with open(full_path, 'r', errors='ignore') as f:
                        for i, line in enumerate(f, 1):
                            if pattern in line:
                                results.append(f"{full_path}:{i}: {line.strip()}")
        return "\n".join(results[:50]) or "No matches found."
    except Exception as e:
        return f"Grep error: {e}"

def list_files(pattern="**/*"):
    files = python_glob.glob(pattern, recursive=True)
    return "\n".join([f for f in files if "venv" not in f and ".git" not in f][:100])

def web_search(query):
    """Perform a web search using DuckDuckGo."""
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=5)]
            if not results:
                return "No web results found."
            
            out = []
            for r in results:
                out.append(f"Title: {r['title']}\nLink: {r['href']}\nSnippet: {r['body']}\n")
            return "\n---\n".join(out)
    except ImportError:
        return "Error: 'duckduckgo-search' package not installed. Please run 'pip install duckduckgo-search'."
    except Exception as e:
        return f"Web search error: {e}"

def system_find(name, root=None):
    """Search for a file/directory by name with sensible defaults and timeout."""
    # Prioritize home directory if no root is specified
    search_root = root or os.path.expanduser("~")
    
    try:
        # Limit depth and time to prevent hangs
        cmd = f"find {search_root} -maxdepth 4 -name '*{name}*' -not -path '*/.*' 2>/dev/null | head -n 20"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        output = result.stdout.strip()
        
        if not output and not root:
            # If not found in home, try / (restricted)
            cmd = f"find / -maxdepth 3 -name '*{name}*' -not -path '*/.*' 2>/dev/null | head -n 10"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20)
            output = result.stdout.strip()
            
        return output or "No matching files found within timeout limits."
    except subprocess.TimeoutExpired:
        return "Search timed out. Please provide a more specific root path."
    except Exception as e:
        return f"System search error: {e}"
