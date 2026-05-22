"""
Perplexity-like web agent using an official search API + LLM summarization.

Requires:
- BING subscription key (BING_API_KEY env or config.api_keys.bing)
- core.services.call_model or core.brain.think available for summarization

NOTE: Respect robots and terms of service for any search API.
"""

import os
import requests
import json
from typing import List, Dict, Optional
from core.config import load_config
from core import services as svc
from rich.console import Console

console = Console()

BING_SEARCH_URL = "https://api.bing.microsoft.com/v7.0/search"

def bing_search(query: str, count: int = 6, offset: int = 0) -> Dict:
    # Try Keychain via svc first
    key = svc.get_api_key("bing") or os.getenv("BING_API_KEY") or load_config().get("api_keys", {}).get("bing")
    if not key:
        return {"ok": False, "error": "Bing API key not configured. Set BING_API_KEY or link 'bing' in /connect."}
    headers = {"Ocp-Apim-Subscription-Key": key}
    params = {"q": query, "count": count, "offset": offset, "mkt": "en-US", "safeSearch": "Moderate"}
    try:
        r = requests.get(BING_SEARCH_URL, headers=headers, params=params, timeout=10)
        if r.status_code != 200:
            return {"ok": False, "error": f"Bing error {r.status_code}: {r.text}"}
        return {"ok": True, "raw": r.json()}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def extract_search_snippets(bing_json: Dict) -> List[Dict]:
    results = []
    if not bing_json:
        return results
    webPages = bing_json.get("webPages", {}).get("value", [])
    for w in webPages:
        results.append({"name": w.get("name"), "url": w.get("url"), "snippet": w.get("snippet")})
    return results

def synthesize_answer(query: str, snippets: List[Dict], provider: str = None, model: str = None) -> Dict:
    """
    Ask the model to synthesize a short answer with citations.
    Returns {'ok':True, 'answer':str, 'sources':[...]} or error.
    """
    if not snippets:
        return {"ok": False, "error": "No search snippets provided for synthesis."}

    # Build a compact context with bullets of source URL + snippet
    ctx_lines = []
    for i, s in enumerate(snippets, 1):
        ctx_lines.append(f"[{i}] {s['url']} - {s.get('snippet','')}")
    context = "\n".join(ctx_lines[:8])
    
    prompt = f"""You are a fact-finding assistant. Given the user query and a set of search results (URL + snippet), produce:
1) A concise answer (max 200 words).
2) Inline citations in square brackets referencing the search result number, e.g. [1], [2].
3) A short list of sources (number, title, url).

User Query:
{query}

Search Results:
{context}

Constraints:
- Do not hallucinate sources.
- Only use the provided snippets when supporting claims.
Return output in two parts separated by "###": first the answer, then the sources (one per line).
"""
    # Use brain.think directly since it has the best formatting and fallback logic
    from core.brain import think
    res = think("Web Research Integrator", prompt, model=model)
    
    if not isinstance(res, dict) or not res.get("ok"):
        error_msg = res.get("error") if isinstance(res, dict) else str(res)
        return {"ok": False, "error": error_msg}

    out = res.get("text", "")
    
    # split by separator
    parts = out.split("###")
    answer = parts[0].strip() if parts else out.strip()
    sources = []
    if len(parts) > 1:
        sources = [s.strip() for s in parts[1].strip().splitlines() if s.strip()]
    
    return {
        "ok": True, 
        "answer": answer, 
        "sources": sources, 
        "provider": res.get("provider"),
        "model": res.get("model")
    }
