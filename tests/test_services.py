import pytest
from unittest.mock import patch, MagicMock
import os
import sys

# Ensure we can import core
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.services import repair_ollama, call_model

@patch('core.services.validate_ollama')
@patch('core.services.load_config')
@patch('core.services.save_config')
def test_repair_ollama_success(mock_save, mock_load, mock_validate):
    mock_load.return_value = {}
    mock_validate.return_value = {"ok": True, "provider": "ollama", "endpoint": "http://localhost:11434/api/tags"}
    
    # Run repair with no OS app opening and no prompts
    report = repair_ollama(host="http://localhost:11434", open_app_if_mac=False, prompt_for_host=False)
    
    assert report["fixed"] is True
    assert "http://localhost:11434" in report["attempts"][0]["host"]
    mock_save.assert_called_once()
    saved_cfg = mock_save.call_args[0][0]
    assert saved_cfg["ollama_host"] == "http://localhost:11434"

@patch('core.services.validate_ollama')
@patch('core.services.load_config')
@patch('core.services.save_config')
def test_repair_ollama_auth_required(mock_save, mock_load, mock_validate):
    mock_load.return_value = {}
    mock_validate.return_value = {"ok": False, "error_type": "auth", "endpoint": "http://localhost:11434/api/tags"}
    
    # Run repair 
    report = repair_ollama(host="http://localhost:11434", open_app_if_mac=False, prompt_for_host=False)
    
    assert report["fixed"] is False # auth means it needs user intervention, but we persist it
    # ensure it was saved
    mock_save.assert_called_once()
    saved_cfg = mock_save.call_args[0][0]
    assert saved_cfg["ollama_host"] == "http://localhost:11434"

@patch('core.services._call_openai_chat')
@patch('core.services.get_api_key')
def test_call_model_openai(mock_get_key, mock_call_openai):
    mock_get_key.return_value = "fake_key"
    mock_call_openai.return_value = {"ok": True, "text": "Hello"}
    
    res = call_model(provider="openai", model="gpt-4o", messages_or_text="Hi")
    assert res["ok"] is True
    assert res["text"] == "Hello"
    mock_call_openai.assert_called_once()
