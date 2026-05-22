from tools.shell import run

def brew_install(package):
    print(f"Installing {package} via Homebrew...")
    return run(f"brew install {package}")

def git_install(repo_url, dest="."):
    print(f"Cloning {repo_url}...")
    return run(f"git clone {repo_url} {dest}")

def curl_install(url, output_path):
    print(f"Downloading {url} to {output_path}...")
    return run(f"curl -L {url} -o {output_path}")
