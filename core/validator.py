import json
import shutil
import subprocess
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

    def _run_test_command(self, test_cmd):
        """Actually executes a registered test command.

        Returns (rc, stdout, stderr), or (None, "", msg) when the command
        is not a real executable command (e.g. a menu label).
        """
        first = test_cmd.split()[0] if test_cmd.split() else ""
        if not first or not shutil.which(first):
            return None, "", f"'{first}' is not an installed command; cannot execute."
        try:
            proc = subprocess.run(test_cmd, shell=True, capture_output=True, text=True, timeout=120)
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return 124, "", "test command timed out"
        except Exception as e:
            return 1, "", str(e)

    def run_tests(self):
        console.print("[bold cyan]🚀 STARTING STRICT VALIDATION MODE[/bold cyan]")
        results = {}
        for capability, (task, test_cmd) in self.registry.items():
            console.print(f"\n[bold]Testing {capability}...[/bold]")

            # 1. Execute the registered test command for real
            rc, out, err = self._run_test_command(test_cmd)
            if rc is None:
                console.print(f"[yellow]⚠️ {capability}: {err} Skipped.[/yellow]")
                results[capability] = "Skipped (not executable)"
                continue

            # 2. Check generated-code heuristic only as an advisory
            res = think_structured("Task", f"Execute this task and ensure code is compilable/functional: {task}")
            code = res.get("text", "") if isinstance(res, dict) else ""
            if code and self.detect_hallucination(code):
                console.print(f"[yellow]⚠️ Hallucination indicators in generated code for {capability}.[/yellow]")

            # 3. Verdict comes from the actual test command result
            if rc == 0:
                console.print(f"[green]✅ {capability} passed validation.[/green]")
                results[capability] = "Passed"
            else:
                console.print(f"[red]❌ {capability} failed (rc={rc}).[/red]")
                if err or out:
                    console.print(f"[dim]{(err or out)[:500]}[/dim]")
                results[capability] = f"Failed (rc={rc})"

        console.print("[bold cyan]🚀 VALIDATION COMPLETE[/bold cyan]")
        return results
