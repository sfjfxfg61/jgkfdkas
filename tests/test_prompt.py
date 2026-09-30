from ai_companion import build_system_prompt


def test_prompt_is_honest_without_repeating_disclosure_and_uses_memory() -> None:
    prompt = build_system_prompt(
        "en",
        "warm",
        [{"memory_key": "project", "memory_value": "builds a Telegram bot"}],
        2,
    )
    assert "If asked whether replies are automated, answer honestly" in prompt
    assert "Never claim to be human" in prompt
    assert "Do not perform romantic or sexual roleplay" in prompt
    assert "builds a Telegram bot" in prompt
    assert "Relationship level: 2/4" in prompt
