import faiss
import numpy as np
import os
import pickle
import requests
from pathlib import Path
from core.config import get_env_with_config

OLLAMA_HOST = get_env_with_config("ollama_host") or "http://localhost:11434"
OLLAMA_EMBED_URL = f"{OLLAMA_HOST}/api/embeddings"
MODEL = get_env_with_config("jarvis_model") or "llama3"

# Move storage to ~/.jarvis/memory
MEMORY_DIR = Path.home() / ".jarvis" / "memory"
DB_PATH = MEMORY_DIR / "memory_store.pkl"
INDEX_PATH = MEMORY_DIR / "memory.index"

_index = None
_store = []

def _get_embedding(text):
    try:
        r = requests.post(OLLAMA_EMBED_URL, json={
            "model": MODEL,
            "prompt": text
        })
        r.raise_for_status()
        return r.json()["embedding"]
    except Exception as e:
        # Silently fail for embeddings to not disrupt the UI flow
        return None

def _get_index(dim=4096):
    global _index, _store
    if _index is None:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        if INDEX_PATH.exists():
            _index = faiss.read_index(str(INDEX_PATH))
            if DB_PATH.exists():
                with open(DB_PATH, "rb") as f:
                    _store = pickle.load(f)
        else:
            _index = faiss.IndexFlatL2(dim)
    return _index

def add(text, metadata=None):
    """Store a memory with optional metadata."""
    if metadata:
        entry = f"[{metadata}] {text}"
    else:
        entry = text

    emb = _get_embedding(entry)
    if emb is None: return
    
    index = _get_index(dim=len(emb))
    index.add(np.array([emb]).astype("float32"))
    _store.append(entry)
    
    # Save
    faiss.write_index(index, str(INDEX_PATH))
    with open(DB_PATH, "wb") as f:
        pickle.dump(_store, f)

def search(q, k=5):
    emb = _get_embedding(q)
    if emb is None: return []
    
    index = _get_index(dim=len(emb))
    if index.ntotal == 0:
        return []
        
    D, I = index.search(np.array([emb]).astype("float32"), k)
    return [_store[i] for i in I[0] if i < len(_store)]

def clear():
    """Wipe all stored memories."""
    global _index, _store
    _index = None
    _store = []
    if INDEX_PATH.exists():
        os.remove(INDEX_PATH)
    if DB_PATH.exists():
        os.remove(DB_PATH)
    return "Memory successfully cleared."

def get_stats():
    """Return memory statistics."""
    index = _get_index()
    return {
        "count": len(_store),
        "index_size": index.ntotal if index else 0
    }
