import os
import ast

def analyze_complexity(file_path):
    if not os.path.exists(file_path):
        return {"functions": 0, "classes": 0, "lines": 0, "complexity_score": 0, "error": f"File {file_path} not found."}
    
    metrics = {
        "functions": 0,
        "classes": 0,
        "lines": 0,
        "complexity_score": 0
    }

    try:
        with open(file_path, "r") as f:
            content = f.read()
            metrics["lines"] = len(content.splitlines())
            tree = ast.parse(content)
    except Exception as e:
        # Fallback for non-parseable files (e.g., Python 2)
        return metrics

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            metrics["functions"] += 1
            # Simple complexity: count branches
            for subnode in ast.walk(node):
                if isinstance(subnode, (ast.If, ast.While, ast.For, ast.With, ast.Try, ast.ExceptHandler)):
                    metrics["complexity_score"] += 1
        elif isinstance(node, ast.ClassDef):
            metrics["classes"] += 1

    return metrics

def project_summary(root_dir="."):
    summary = {
        "total_files": 0,
        "total_lines": 0,
        "languages": {},
        "hotspots": [] # Files with high complexity
    }

    for root, dirs, files in os.walk(root_dir):
        if any(x in root for x in ["venv", ".git", "__pycache__", "dist"]):
            continue
        
        for file in files:
            summary["total_files"] += 1
            ext = os.path.splitext(file)[1]
            summary["languages"][ext] = summary["languages"].get(ext, 0) + 1
            
            if ext == ".py":
                full_path = os.path.join(root, file)
                m = analyze_complexity(full_path)
                summary["total_lines"] += m["lines"]
                if m["complexity_score"] > 10:
                    summary["hotspots"].append({"path": full_path, "score": m["complexity_score"]})

    return summary
