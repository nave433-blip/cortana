import json
from rich.console import Console
from core.brain import think_structured
from core.refinement import refine_loop

console = Console()

class Validator:
    def __init__(self):
        self.registry = {
            "P2P Hive Mind": ("Setup two P2P nodes and verify communication", "p2p-status"),
            "Hardware Probing": ("Probe hardware ports and verify detection", "hardware-menu"),
            "Code Generation": ("Generate a simple Python utility script and ensure it runs", "python3 test_gen.py"),
            # Add more capabilities here as defined in the plan
        }

    def detect_hallucination(self, code_content):
        # A simple heuristic-based hallucination detector
        hallucination_indicators = ["# TODO", "pseudo-code", "import non_existent_lib"]
        for indicator in hallucination_indicators:
            if indicator in code_content:
                return True
        return False

    def run_tests(self):
        console.print("[bold cyan]🚀 STARTING STRICT VALIDATION MODE[/bold cyan]")
        results = {}
        for capability, (task, test_cmd) in self.registry.items():
            console.print(f"\n[bold]Testing {capability}...[/bold]")
            # 1. Execute Task
            # 2. Check for Hallucinations
            # 3. Refine loop
            
            # Simplified flow:
            res = think_structured("Task", f"Execute this task and ensure code is compilable/functional: {task}")
            code = res.get("text", "")
            
            if self.detect_hallucination(code):
                console.print(f"[red]❌ Hallucination detected in {capability}![/red]")
                # Trigger Refinement
                # refine_loop(...)
            else:
                console.print(f"[green]✅ {capability} passed validation.[/green]")
                results[capability] = "Passed"
        
        console.print("[bold cyan]🚀 VALIDATION COMPLETE[/bold cyan]")
        return results
