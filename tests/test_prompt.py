from ai_companion import build_system_prompt


def test_prompt_discloses_ai_and_uses_memory() -> None:
    prompt = build_system_prompt(
        "en",
        "warm",
        [{"memory_key": "project", "memory_value": "builds a Telegram bot"}],
        2,
    )
    assert "openly disclosed AI companion" in prompt
    assert "Never claim to be human" in prompt
    assert "Do not perform romantic or sexual roleplay" in prompt
    assert "builds a Telegram bot" in prompt
    assert "Relationship level: 2/4" in prompt
