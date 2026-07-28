"""Tests for Instagram webhook helpers."""

INSTAGRAM_MID_SAMPLE = (
    "aWdfZAG1faXRlbToxOklHTWVzc2FnZAUlEOjE3ODQxNDQ5MDYzMzQ0NzQ3OjM0MDI4MjM2Njg0"
    "MTcxMDMwMTI0NDI1OTg2ODQyMTIyNTY2NzQ0NDozMjkzMjQ1NDcxNDg3NTkzMjk0ODM5Njcy"
    "MTg2NzU4NzU4NAZDZD"
)


def test_instagram_mid_fits_platform_message_id_column():
    assert len(INSTAGRAM_MID_SAMPLE) > 128
    assert len(INSTAGRAM_MID_SAMPLE) <= 512
