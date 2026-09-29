"""The transcription model the operator selects must be the one that runs."""
import os

import pytest

from backend.models.asr import ASROptions
from backend.models.session import SessionSettings
from backend.pipeline.offline_pipeline import OfflinePipeline
from backend.providers.asr.registry import (
    DEFAULT_MODEL,
    MODELS,
    get_asr_provider,
    list_asr_models,
    model_is_available,
    primary_model_id,
)
from backend.providers.asr.svanita import SvanitaParakeetProvider


def test_catalogue_covers_a_local_and_a_cloud_option():
    assert DEFAULT_MODEL == "svanita_0_6b"
    assert any(m.local for m in MODELS.values()), "at least one on-device model is required"
    assert any(not m.local for m in MODELS.values()), "a cloud option should remain selectable"
    assert sum(1 for m in MODELS.values() if m.recommended) == 1, "exactly one recommended model"


def test_every_model_declares_a_builder():
    for model in MODELS.values():
        assert callable(model.builder), f"{model.id} has no builder"
        assert model.languages, f"{model.id} declares no languages"
        assert model.description, f"{model.id} has no description for the UI"


def test_cloud_models_report_unavailable_without_a_key():
    for model in MODELS.values():
        if model.requires_api_key and not os.environ.get(model.requires_api_key):
            assert model_is_available(model.id) is False
            entry = next(m for m in list_asr_models() if m["id"] == model.id)
            assert entry["available"] is False
            assert entry["unavailable_reason"]


def test_requesting_a_cloud_model_without_a_key_is_refused():
    cloud = next((m for m in MODELS.values() if m.requires_api_key), None)
    if cloud is None:
        pytest.skip("no cloud model configured")
    if os.environ.get(cloud.requires_api_key):
        pytest.skip("API key is configured in this environment")
    with pytest.raises(RuntimeError, match=cloud.requires_api_key):
        get_asr_provider(cloud.id)


def test_unknown_model_ids_fall_back_instead_of_crashing():
    provider = get_asr_provider("a-model-that-does-not-exist")
    assert isinstance(provider, SvanitaParakeetProvider)


def test_providers_are_cached_because_models_are_expensive_to_load():
    first = get_asr_provider(DEFAULT_MODEL)
    second = get_asr_provider(DEFAULT_MODEL)
    assert first is second


def test_environment_overrides_the_default_model(monkeypatch):
    monkeypatch.setenv("PRIMARY_ASR_MODEL", "whisper_small_int8")
    assert primary_model_id() == "whisper_small_int8"
    monkeypatch.setenv("PRIMARY_ASR_MODEL", "not-a-model")
    assert primary_model_id() == DEFAULT_MODEL


def test_list_asr_models_is_usable_by_the_ui():
    entries = list_asr_models()
    assert {e["id"] for e in entries} == set(MODELS)
    for entry in entries:
        assert "builder" not in entry, "callables must not be serialised to the client"
        assert isinstance(entry["languages"], list)
        assert isinstance(entry["available"], bool)


def test_pipeline_defaults_to_the_configured_model():
    assert OfflinePipeline().default_asr_model == primary_model_id()


def test_session_settings_persist_the_chosen_model():
    settings = SessionSettings(asr_model="whisper_small_int8")
    assert settings.asr_model == "whisper_small_int8"
    assert settings.model_dump()["asr_model"] == "whisper_small_int8"


def test_asr_options_carry_the_registry_id_not_an_api_model_name():
    options = ASROptions(model="svanita_0_6b")
    assert options.model == "svanita_0_6b"
