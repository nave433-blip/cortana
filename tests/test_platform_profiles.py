"""Round C: profiles — lifecycle, switching, overrides, memory scope."""
import json

import pytest

import core.config as config_mod


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config_mod, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
    import core.profiles as profiles_mod
    monkeypatch.setattr(profiles_mod, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(profiles_mod, "console",
                        __import__("rich.console", fromlist=["Console"]).Console(file=open("/dev/null", "w")))
    return tmp_path


def test_default_profile_always_listed(isolated):
    from core.profiles import list_profiles, get_active_profile
    names = [p["name"] for p in list_profiles()]
    assert "default" in names
    assert get_active_profile() == "default"


def test_create_switch_override(isolated):
    from core.profiles import create_profile, switch_profile, get_active_profile
    from core.settings import get_setting
    assert create_profile("work", description="Work stuff", settings={"theme": "light"})["ok"]
    assert switch_profile("work")["ok"]
    assert get_active_profile() == "work"
    # Profile override wins over global config.
    assert get_setting("theme") == "light"
    # Non-overridden keys fall through to global.
    assert get_setting("compact_mode") is False


def test_create_validates_settings(isolated):
    from core.profiles import create_profile
    res = create_profile("bad", settings={"not_a_setting": 1})
    assert not res["ok"]
    res = create_profile("bad2", settings={"theme": "neon"})
    assert not res["ok"]
    assert create_profile("ok-name_1")["ok"]
    assert not create_profile("bad name!")["ok"]


def test_switch_unknown_fails(isolated):
    from core.profiles import switch_profile
    assert not switch_profile("ghost")["ok"]


def test_delete_profile(isolated, monkeypatch):
    from core.profiles import create_profile, delete_profile, switch_profile, get_active_profile
    monkeypatch.setattr("core.approvals.confirm", lambda *a, **k: True)
    create_profile("temp")
    switch_profile("temp")
    assert delete_profile("temp")["ok"]
    # Active profile falls back to default.
    assert get_active_profile() == "default"
    assert not delete_profile("default")["ok"]


def test_memory_scope_follows_profile(isolated):
    from core.profiles import create_profile, switch_profile, memory_scope
    create_profile("work")
    switch_profile("work")
    assert memory_scope() == "profile:work"
    switch_profile("default")
    assert memory_scope() == "profile:default"


def test_set_profile_setting(isolated):
    from core.profiles import create_profile, set_profile_setting, profile_override
    create_profile("work")
    assert set_profile_setting("work", "theme", "light")["ok"]
    assert profile_override("theme") is None  # not active yet
    assert not set_profile_setting("work", "bogus", "x")["ok"]
    assert not set_profile_setting("default", "theme", "light")["ok"]
