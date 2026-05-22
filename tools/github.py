import requests
import os
from core.config import get_env_with_config

class GitHubTool:
    def __init__(self):
        self.token = get_env_with_config("github_token")
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }

    def call(self, method, endpoint, data=None):
        if not self.token:
            return "Error: GITHUB_TOKEN not configured."
        
        url = f"{self.base_url}/{endpoint}"
        try:
            if method == "GET":
                r = requests.get(url, headers=self.headers)
            elif method == "POST":
                r = requests.post(url, headers=self.headers, json=data)
            elif method == "PATCH":
                r = requests.patch(url, headers=self.headers, json=data)
            
            r.raise_for_status()
            return r.json()
        except Exception as e:
            return f"GitHub API Error: {e}"

    def get_repo_info(self, repo_full_name):
        return self.call("GET", f"repos/{repo_full_name}")

    def create_issue(self, repo_full_name, title, body):
        return self.call("POST", f"repos/{repo_full_name}/issues", {"title": title, "body": body})

    def list_pull_requests(self, repo_full_name):
        return self.call("GET", f"repos/{repo_full_name}/pulls")

    def create_pr(self, repo_full_name, title, body, head, base="main"):
        data = {"title": title, "body": body, "head": head, "base": base}
        return self.call("POST", f"repos/{repo_full_name}/pulls", data)

github_tool = GitHubTool()
