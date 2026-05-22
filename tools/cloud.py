import os
import sys
from core.config import get_env_with_config

# Optional imports handled inside functions to avoid crash if deps fail
def get_dropbox_client():
    try:
        import dropbox
        token = get_env_with_config("dropbox_token")
        if not token: return None
        return dropbox.Dropbox(token)
    except:
        return None

def get_gdrive_service():
    try:
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials
        token = get_env_with_config("gdrive_token")
        if not token: return None
        # This assumes a pre-authorized token for simplicity in CLI
        creds = Credentials(token)
        return build('drive', 'v3', credentials=creds)
    except:
        return None

def list_dropbox(path=""):
    dbx = get_dropbox_client()
    if not dbx: return "Error: Dropbox not configured or dependency missing."
    try:
        res = dbx.files_list_folder(path)
        return [entry.name for entry in res.entries]
    except Exception as e:
        return f"Dropbox Error: {e}"

def list_gdrive(query="'root' in parents"):
    service = get_gdrive_service()
    if not service: return "Error: Google Drive not configured or dependency missing."
    try:
        results = service.files().list(q=query, pageSize=10, fields="files(id, name)").execute()
        return [f['name'] for f in results.get('files', [])]
    except Exception as e:
        return f"GDrive Error: {e}"

def get_icloud_path():
    if sys.platform == "darwin":
        path = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs")
        if os.path.exists(path):
            return path
    return None

def list_icloud(subpath=""):
    base = get_icloud_path()
    if not base: return "Error: iCloud Drive not found or not on macOS."
    target = os.path.join(base, subpath)
    try:
        return os.listdir(target)
    except Exception as e:
        return f"iCloud Error: {e}"
