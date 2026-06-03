from app.services.studio_model_bootstrap import (
    DEFAULT_FACE_MERGE_PROMPT,
    resolve_face_merge_prompt,
)


def test_resolve_face_merge_prompt_empty_uses_default():
    assert resolve_face_merge_prompt("") == DEFAULT_FACE_MERGE_PROMPT
    assert resolve_face_merge_prompt("   ") == DEFAULT_FACE_MERGE_PROMPT


def test_resolve_face_merge_prompt_custom():
    custom = "My custom merge prompt"
    assert resolve_face_merge_prompt(custom) == custom
