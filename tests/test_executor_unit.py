from unittest.mock import MagicMock

from tvision.actions import Executor


def _make() -> tuple[Executor, MagicMock]:
    browser = MagicMock()
    browser.page = MagicMock()
    browser.cursor = (0, 0)
    settings = MagicMock(type_delay_ms=20, settle_delay_ms=0)
    return Executor(browser, settings), browser


def test_click_passes_absolute_coords():
    ex, browser = _make()
    status = ex.dispatch("click", {"x": 100, "y": 200})
    browser.page.mouse.click.assert_called_once()
    args, kwargs = browser.page.mouse.click.call_args
    assert args == (100, 200)
    assert kwargs["button"] == "left"
    assert kwargs["modifiers"] == []
    assert "clicked" in status
    assert browser.cursor == (100, 200)


def test_click_modifiers_normalized():
    ex, browser = _make()
    ex.dispatch("click", {"x": 1, "y": 2, "modifiers": ["ctrl", "shift"]})
    _, kwargs = browser.page.mouse.click.call_args
    assert kwargs["modifiers"] == ["Control", "Shift"]


def test_type_uses_keyboard_type():
    ex, browser = _make()
    status = ex.dispatch("type", {"text": "hello"})
    browser.page.keyboard.type.assert_called_once()
    assert "5 chars" in status


def test_key_translates_combo():
    ex, browser = _make()
    ex.dispatch("key", {"combo": "ctrl+return"})
    browser.page.keyboard.press.assert_called_once_with("Control+Enter")


def test_scroll_wheels_at_position():
    ex, browser = _make()
    ex.dispatch("scroll", {"x": 50, "y": 60, "dy": 400})
    browser.page.mouse.move.assert_called_with(50, 60)
    browser.page.mouse.wheel.assert_called_with(0, 400)


def test_unknown_tool_returns_error_string():
    ex, _ = _make()
    status = ex.dispatch("nonexistent", {})
    assert status.startswith("error")


def test_bad_args_returns_error_string():
    ex, _ = _make()
    status = ex.dispatch("click", {"x": 1})
    assert status.startswith("error")
