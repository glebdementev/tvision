from unittest.mock import MagicMock

from tvision.actions import Executor


def _make() -> tuple[Executor, MagicMock]:
    browser = MagicMock()
    browser.page = MagicMock()
    browser.cursor = (0, 0)
    settings = MagicMock(
        type_delay_ms=20,
        settle_delay_ms=0,
        viewport_width=1280,
        viewport_height=720,
    )
    return Executor(browser, settings), browser


def test_left_click_rescales_normalized_coords():
    ex, browser = _make()
    # 500/1000 * 1280 = 640; 500/1000 * 720 = 360
    status = ex.dispatch(
        "computer_use", {"action": "left_click", "coordinate": [500, 500]}
    )
    browser.page.mouse.click.assert_called_once()
    args, kwargs = browser.page.mouse.click.call_args
    assert args == (640, 360)
    assert kwargs["button"] == "left"
    assert kwargs["click_count"] == 1
    assert browser.cursor == (640, 360)
    assert "click" in status


def test_left_click_without_coord_uses_cursor():
    ex, browser = _make()
    browser.cursor = (123, 45)
    ex.dispatch("computer_use", {"action": "left_click"})
    args, _ = browser.page.mouse.click.call_args
    assert args == (123, 45)


def test_double_click_uses_click_count_2():
    ex, browser = _make()
    ex.dispatch(
        "computer_use", {"action": "double_click", "coordinate": [0, 0]}
    )
    _, kwargs = browser.page.mouse.click.call_args
    assert kwargs["click_count"] == 2


def test_triple_click_uses_click_count_3():
    ex, browser = _make()
    ex.dispatch(
        "computer_use", {"action": "triple_click", "coordinate": [0, 0]}
    )
    _, kwargs = browser.page.mouse.click.call_args
    assert kwargs["click_count"] == 3


def test_right_and_middle_click_buttons():
    ex, browser = _make()
    ex.dispatch("computer_use", {"action": "right_click", "coordinate": [10, 10]})
    _, kwargs = browser.page.mouse.click.call_args
    assert kwargs["button"] == "right"
    ex.dispatch("computer_use", {"action": "middle_click", "coordinate": [10, 10]})
    _, kwargs = browser.page.mouse.click.call_args
    assert kwargs["button"] == "middle"


def test_rescale_clamps_at_999():
    ex, browser = _make()
    ex.dispatch("computer_use", {"action": "left_click", "coordinate": [999, 999]})
    args, _ = browser.page.mouse.click.call_args
    # 999/1000 * 1280 = 1278.72 -> 1279; 999/1000 * 720 = 719.28 -> 719
    assert args == (1279, 719)


def test_mouse_move_rescales():
    ex, browser = _make()
    ex.dispatch("computer_use", {"action": "mouse_move", "coordinate": [250, 500]})
    # 250/1000 * 1280 = 320; 500/1000 * 720 = 360
    browser.page.mouse.move.assert_called_once_with(320, 360)
    assert browser.cursor == (320, 360)


def test_type_uses_keyboard_type():
    ex, browser = _make()
    status = ex.dispatch("computer_use", {"action": "type", "text": "hello"})
    browser.page.keyboard.type.assert_called_once()
    assert "5 chars" in status


def test_key_translates_combo():
    ex, browser = _make()
    ex.dispatch("computer_use", {"action": "key", "text": "ctrl+return"})
    browser.page.keyboard.press.assert_called_once_with("Control+Enter")


def test_scroll_down_to_wheel_delta():
    ex, browser = _make()
    ex.dispatch(
        "computer_use",
        {
            "action": "scroll",
            "coordinate": [500, 500],
            "scroll_direction": "down",
            "scroll_amount": 4,
        },
    )
    browser.page.mouse.move.assert_called_with(640, 360)
    browser.page.mouse.wheel.assert_called_with(0, 400)


def test_scroll_up_is_negative_dy():
    ex, browser = _make()
    ex.dispatch(
        "computer_use",
        {"action": "scroll", "scroll_direction": "up", "scroll_amount": 2},
    )
    browser.page.mouse.wheel.assert_called_with(0, -200)


def test_drag_rescales_both_endpoints():
    ex, browser = _make()
    ex.dispatch(
        "computer_use",
        {
            "action": "left_click_drag",
            "coordinate": [0, 0],
            "coordinate2": [999, 999],
        },
    )
    moves = browser.page.mouse.move.call_args_list
    assert moves[0].args == (0, 0)
    assert moves[1].args == (1279, 719)


def test_goto_navigates():
    ex, browser = _make()
    status = ex.dispatch(
        "computer_use", {"action": "goto", "url": "https://example.com"}
    )
    browser.page.goto.assert_called_once_with("https://example.com")
    assert "navigated" in status


def test_unknown_action_returns_error():
    ex, _ = _make()
    status = ex.dispatch("computer_use", {"action": "nonexistent"})
    assert status.startswith("error")


def test_missing_action_returns_error():
    ex, _ = _make()
    status = ex.dispatch("computer_use", {})
    assert status.startswith("error")


def test_unknown_tool_returns_error():
    ex, _ = _make()
    status = ex.dispatch("not_computer_use", {})
    assert status.startswith("error")
