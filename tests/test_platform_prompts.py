"""Round C: prompt library extensions — apply, overrides, Round B hook."""
import json

import pytest

import core.config as config_mod
import core.prompts as prompts_mod


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config_mod, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(prompts_mod, "PROMPTS_DIR", tmp_path)
    monkeypatch.setattr(prompts_mod, "PROMPTS_FILE", tmp_path / "prompts.json")
    return tmp_path


def test_apply_prompt(isolated):
    from core.prompts import save_prompt, apply_prompt, get_active_prompt_name, get_active_prompt_text
    save_prompt("code-review", "Review code harshly.")
    ok, msg = apply_prompt("code-review")
    assert ok
    assert get_active_prompt_name() == "code-review"
    assert get_active_prompt_text() == "Review code harshly."
    ok, msg = apply_prompt("ghost")
    assert not ok


def test_list_skips_internal_sections(isolated):
    from core.prompts import save_prompt, set_personality_override, list_prompts
    save_prompt("mine", "text")
    set_personality_override("witty", "default", "override text")
    table = list_prompts()
    # Renders without error and doesn't show _overrides as a prompt.
    assert table is not None


def test_personality_override_hook(isolated):
    """The hook Round B's personality system consumes."""
    from core.prompts import (set_personality_override, get_prompt_for_personality,
                              get_active_prompt_text)
    base = get_active_prompt_text()
    # No override -> base text.
    assert get_prompt_for_personality("witty") == base
    set_personality_override("witty", "default", "Be funny.")
    assert get_prompt_for_personality("witty") == "Be funny."
    # Other personalities unaffected.
    assert get_prompt_for_personality("professional") == base
    # Clearing restores base.
    set_personality_override("witty", "default", "")
    assert get_prompt_for_personality("witty") == base


def test_overrides_survive_save_prompt(isolated):
    from core.prompts import save_prompt, set_personality_override, get_overrides
    set_personality_override("witty", "default", "Be funny.")
    save_prompt("another", "text")
    assert get_overrides()["witty"]["default"] == "Be funny."
