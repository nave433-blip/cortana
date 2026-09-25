"""Round C: projects — lifecycle, attachments, context injection."""
import pytest

import core.config as config_mod


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config_mod, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
    import core.projects as projects_mod
    monkeypatch.setattr(projects_mod, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(projects_mod, "console",
                        __import__("rich.console", fromlist=["Console"]).Console(file=open("/dev/null", "w")))
    return tmp_path


def test_create_and_list(isolated):
    from core.projects import create_project, list_projects
    res = create_project("My App", instructions="Be terse.")
    assert res["ok"] and res["slug"] == "my-app"
    slugs = [p["slug"] for p in list_projects()]
    assert "my-app" in slugs


def test_open_close_active(isolated):
    from core.projects import create_project, open_project, close_project, get_active_project
    create_project("My App")
    assert open_project("my-app")["ok"]
    assert get_active_project() == "my-app"
    assert not open_project("ghost")["ok"]
    close_project()
    assert get_active_project() == ""


def test_attachments(isolated, tmp_path):
    from core.projects import create_project, add_attachment, remove_attachment, load_project
    f = tmp_path / "notes.txt"
    f.write_text("hello")
    create_project("Docs")
    assert add_attachment("docs", str(f))["ok"]
    assert not add_attachment("docs", str(f))["ok"]  # duplicate
    assert not add_attachment("docs", "/does/not/exist")["ok"]
    assert str(f) in load_project("docs")["attachments"]
    assert remove_attachment("docs", str(f))["ok"]
    assert not remove_attachment("docs", str(f))["ok"]


def test_context_block_includes_instructions_and_files(isolated, tmp_path):
    from core.projects import (create_project, open_project, add_attachment,
                               project_context_block, inject_into_system_prompt)
    f = tmp_path / "main.py"
    f.write_text("print('hi')")
    create_project("Code", instructions="Always explain.")
    add_attachment("code", str(f))
    open_project("code")
    block = project_context_block()
    assert "Always explain." in block
    assert "print('hi')" in block
    injected = inject_into_system_prompt("BASE")
    assert injected.startswith("[Project:")
    assert injected.endswith("BASE")


def test_no_active_project_noop(isolated):
    from core.projects import project_context_block, inject_into_system_prompt
    assert project_context_block() == ""
    assert inject_into_system_prompt("BASE") == "BASE"


def test_delete_project(isolated, monkeypatch):
    from core.projects import create_project, delete_project, list_projects, open_project
    monkeypatch.setattr("core.approvals.confirm", lambda *a, **k: True)
    create_project("Gone")
    open_project("gone")
    assert delete_project("gone")["ok"]
    assert "gone" not in [p["slug"] for p in list_projects()]
    assert not delete_project("ghost")["ok"]


def test_chat_logging(isolated):
    from core.projects import create_project, log_chat_turn
    create_project("Logged")
    log_chat_turn("logged", "user", "hello")
    logs = list((isolated / "projects" / "logged" / "chats").glob("*.jsonl"))
    assert len(logs) == 1
    assert "hello" in logs[0].read_text()
