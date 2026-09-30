from keyboards import main_kb


def test_main_keyboard_is_minimal() -> None:
    markup = main_kb("en")
    callbacks = {
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    }
    assert callbacks == {"nav:premium", "nav:about"}
