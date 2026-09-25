"""Outlook / Microsoft 365 connector via Microsoft Graph (read-only).

Requires an Azure app registration: set ``ms_client_id`` in Cortana's
settings (``cortana settings set ms_client_id <id>``) — any "personal
Microsoft account" multi-tenant app works. We are explicit about this:
without a registered client id the connector reports ``connected: False``
and tells you exactly what to do. No connection is ever faked.
"""
from __future__ import annotations

from typing import Any, Dict, List

from core.connectors.base import Connector
from core.connectors.oauth import run_pkce_flow, api_get
from core.config import load_config
from rich.console import Console

console = Console()

MS_AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
MS_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
GRAPH = "https://graph.microsoft.com/v1.0"


class OutlookConnector(Connector):
    id = "outlook"
    display = "Outlook / Microsoft 365"
    description = "Read Outlook mail and calendar via Microsoft Graph (read-only)."
    auth_kind = "oauth2"
    scopes = ["openid", "profile", "email", "Mail.Read", "Calendars.Read"]

    def _client_id(self) -> str:
        return (load_config().get("ms_client_id", "") or "").strip()

    def _needs_message(self) -> str:
        if not self._client_id():
            return ("Not configured: register an app at https://portal.azure.com "
                    "(personal MS accounts supported), then run "
                    "`cortana settings set ms_client_id <application-id>` "
                    f"and `/connector connect {self.id}`.")
        return f"Run `/connector connect {self.id}` to link your Microsoft account."

    def connect(self) -> Dict[str, Any]:
        cid = self._client_id()
        if not cid:
            console.print(f"[yellow]{self._needs_message()}[/yellow]")
            return {"ok": False, "error": "ms_client_id not set"}
        console.print("[cyan]Opening browser to link your Microsoft account…[/cyan]")
        token = run_pkce_flow(MS_AUTH_URL, MS_TOKEN_URL, cid, self.scopes)
        if "error" in token:
            return {"ok": False, "error": token["error"]}
        me = api_get(f"{GRAPH}/me", token["access_token"],
                     {"$select": "mail,userPrincipalName,displayName"})
        token["account"] = (me.get("mail") or me.get("userPrincipalName", "")
                            if isinstance(me, dict) else "")
        self.save_token(token)
        return {"ok": True, "account": token.get("account", "")}

    def actions(self) -> Dict[str, Dict[str, Any]]:
        tok = (self.get_token() or {}).get("access_token", "")

        def _summarize(messages: List[Dict[str, Any]]):
            out = []
            for m in messages:
                frm = (m.get("from") or {}).get("emailAddress", {})
                out.append({"id": m.get("id"), "from": frm.get("address", ""),
                            "subject": m.get("subject", ""),
                            "received": m.get("receivedDateTime", ""),
                            "preview": m.get("bodyPreview", "")})
            return out

        def _list_messages(limit: int = 10):
            res = api_get(f"{GRAPH}/me/messages", tok,
                          {"$top": str(min(limit, 50)),
                           "$select": "id,subject,from,receivedDateTime,bodyPreview",
                           "$orderby": "receivedDateTime desc"})
            if "error" in res:
                return {"ok": False, "error": res["error"]}
            return {"ok": True, "messages": _summarize(res.get("value", []))}

        def _search_messages(query: str, limit: int = 10):
            res = api_get(f"{GRAPH}/me/messages", tok,
                          {"$top": str(min(limit, 50)), "$search": f'"{query}"',
                           "$select": "id,subject,from,receivedDateTime,bodyPreview"})
            if "error" in res:
                return {"ok": False, "error": res["error"]}
            return {"ok": True, "messages": _summarize(res.get("value", []))}

        def _read_message(message_id: str):
            res = api_get(f"{GRAPH}/me/messages/{message_id}", tok,
                          {"$select": "subject,from,receivedDateTime,body"})
            if "error" in res:
                return {"ok": False, "error": res["error"]}
            body = (res.get("body") or {}).get("content", "")
            frm = (res.get("from") or {}).get("emailAddress", {})
            return {"ok": True, "from": frm.get("address", ""),
                    "subject": res.get("subject", ""),
                    "received": res.get("receivedDateTime", ""),
                    "body": body[:12000]}

        def _upcoming_events(days: int = 7, limit: int = 20):
            import datetime
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            end = (datetime.datetime.now(datetime.timezone.utc)
                   + datetime.timedelta(days=days)).isoformat()
            res = api_get(f"{GRAPH}/me/calendarview", tok,
                          {"startDateTime": now, "endDateTime": end,
                           "$top": str(min(limit, 50)),
                           "$select": "subject,start,end,location,onlineMeeting",
                           "$orderby": "start/dateTime"})
            if "error" in res:
                return {"ok": False, "error": res["error"]}
            out = []
            for e in res.get("value", []):
                out.append({"subject": e.get("subject", "(no title)"),
                            "start": (e.get("start") or {}).get("dateTime", ""),
                            "end": (e.get("end") or {}).get("dateTime", ""),
                            "location": ((e.get("location") or {}).get("displayName", ""))})
            return {"ok": True, "events": out}

        return {
            "list_messages": {"description": "List recent Outlook messages.",
                              "run": _list_messages},
            "search_messages": {"description": "Search Outlook messages.",
                                "run": _search_messages},
            "read_message": {"description": "Read one message (message_id).",
                             "run": _read_message},
            "upcoming_events": {"description": "List upcoming calendar events.",
                                "run": _upcoming_events},
        }
