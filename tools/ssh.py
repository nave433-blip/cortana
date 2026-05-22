import paramiko
import os
from rich.console import Console

console = Console()

class SSHClient:
    def __init__(self, host, username, password=None, key_path=None):
        self.host = host
        self.username = username
        self.password = password
        self.key_path = key_path
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def connect(self):
        try:
            if self.key_path:
                key = paramiko.RSAKey.from_private_key_file(os.path.expanduser(self.key_path))
                self.client.connect(self.host, username=self.username, pkey=key)
            else:
                self.client.connect(self.host, username=self.username, password=self.password)
            return True
        except Exception as e:
            return f"SSH Connection Error: {e}"

    def execute(self, command):
        try:
            stdin, stdout, stderr = self.client.exec_command(command)
            return {
                "stdout": stdout.read().decode('utf-8'),
                "stderr": stderr.read().decode('utf-8'),
                "exit_status": stdout.channel.recv_exit_status()
            }
        except Exception as e:
            return f"SSH Execution Error: {e}"

    def close(self):
        self.client.close()

def run_remote(host, username, command, password=None, key_path=None):
    client = SSHClient(host, username, password, key_path)
    res = client.connect()
    if res is not True:
        return res
    
    output = client.execute(command)
    client.close()
    return output
