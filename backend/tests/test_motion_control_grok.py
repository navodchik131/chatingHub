from app.services.motion_control_grok import (
    bind_motion_control_seedance_tags,
    extract_shot_analyst_prompt_block,
    load_motion_control_turnaround_prompt,
)


def test_bind_motion_control_seedance_tags():
    raw = "<<<DEPTH_MAP>>> control. Identity <<<CHARACTER_IMAGE>>>."
    out = bind_motion_control_seedance_tags(raw)
    assert "@Video1" in out
    assert "@Image1" in out
    assert "<<<" not in out


def test_extract_shot_analyst_prompt_block_from_fence():
    text = "NOTES later\n```\n[SOURCE MATERIAL]\nHello\n```\nNOTES: cut at 1.2s"
    block = extract_shot_analyst_prompt_block(text)
    assert block.startswith("[SOURCE MATERIAL]")
    assert "Hello" in block


def test_turnaround_prompt_loaded_from_file():
    prompt = load_motion_control_turnaround_prompt()
    assert "ДВУХПАНЕЛЬНЫЙ" in prompt
    assert "16:9" in prompt
