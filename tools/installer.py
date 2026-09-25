import shlex
import shutil
import sys
from typing import Optional
from tools.shell import run

def _linux_install_cmd(package: str) -> Optional[str]:
    """Pick a native package-manager install command on Linux, or None."""
    pkg = shlex.quote(package)
    if shutil.which("apt-get"):
        return f"sudo apt-get install -y {pkg}"
    if shutil.which("dnf"):
        return f"sudo dnf install -y {pkg}"
    if shutil.which("pacman"):
        return f"sudo pacman -S --noconfirm {pkg}"
    if shutil.which("zypper"):
        return f"sudo zypper install -y {pkg}"
    return None

def brew_install(package):
    """Install a system package via Homebrew (macOS) or the native Linux package manager."""
    if shutil.which("brew"):
        print(f"Installing {package} via Homebrew...")
        return run(f"brew install {shlex.quote(package)}")
    if sys.platform == "linux":
        cmd = _linux_install_cmd(package)
        if cmd:
            print(f"Installing {package} via system package manager...")
            return run(cmd)
    return {"ok": False, "error": f"No supported package manager found to install '{package}'."}

def git_install(repo_url, dest="."):
    print(f"Cloning {repo_url}...")
    return run(f"git clone {shlex.quote(repo_url)} {shlex.quote(dest)}")

def curl_install(url, output_path):
    print(f"Downloading {url} to {output_path}...")
    return run(f"curl -L {shlex.quote(url)} -o {shlex.quote(output_path)}")
