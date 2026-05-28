_MOD = {
    "ctrl": "Control",
    "control": "Control",
    "shift": "Shift",
    "alt": "Alt",
    "option": "Alt",
    "meta": "Meta",
    "cmd": "Meta",
    "command": "Meta",
    "super": "Meta",
}

_KEY = {
    "return": "Enter",
    "enter": "Enter",
    "esc": "Escape",
    "escape": "Escape",
    "tab": "Tab",
    "backspace": "Backspace",
    "delete": "Delete",
    "del": "Delete",
    "space": "Space",
    "up": "ArrowUp",
    "down": "ArrowDown",
    "left": "ArrowLeft",
    "right": "ArrowRight",
    "home": "Home",
    "end": "End",
    "pageup": "PageUp",
    "pagedown": "PageDown",
    "insert": "Insert",
}


def to_playwright(combo: str) -> str:
    parts = [p.strip() for p in combo.split("+") if p.strip()]
    if not parts:
        return combo
    out: list[str] = []
    for i, p in enumerate(parts):
        low = p.lower()
        if i < len(parts) - 1:
            out.append(_MOD.get(low, p))
        else:
            out.append(_KEY.get(low, p))
    return "+".join(out)


def normalize_modifiers(mods: list[str] | None) -> list[str]:
    if not mods:
        return []
    return [_MOD.get(m.lower(), m) for m in mods]
