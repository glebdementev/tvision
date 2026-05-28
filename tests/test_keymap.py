from tvision.keymap import normalize_modifiers, to_playwright


def test_single_letter_passthrough():
    assert to_playwright("a") == "a"


def test_named_keys():
    assert to_playwright("return") == "Enter"
    assert to_playwright("esc") == "Escape"
    assert to_playwright("up") == "ArrowUp"
    assert to_playwright("pageup") == "PageUp"


def test_combo_modifiers():
    assert to_playwright("ctrl+a") == "Control+a"
    assert to_playwright("ctrl+shift+t") == "Control+Shift+t"
    assert to_playwright("cmd+c") == "Meta+c"


def test_combo_with_named_last():
    assert to_playwright("shift+Tab") == "Shift+Tab"
    assert to_playwright("ctrl+return") == "Control+Enter"


def test_function_keys_passthrough():
    assert to_playwright("F1") == "F1"


def test_modifier_normalization():
    assert normalize_modifiers(["ctrl", "shift"]) == ["Control", "Shift"]
    assert normalize_modifiers(None) == []
    assert normalize_modifiers([]) == []
