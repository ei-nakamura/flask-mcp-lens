from __future__ import annotations

import re

CONVERTER_PATTERNS: dict[str, str] = {
    "string": r"[^/]+",
    "default": r"[^/]+",
    "int": r"[0-9]+",
    "float": r"[0-9]+(?:\.[0-9]+)?",
    "path": r".+",
    "uuid": (
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    ),
}

_VARIABLE_RE = re.compile(r"<(?:([a-zA-Z_][a-zA-Z0-9_]*):)?([a-zA-Z_][a-zA-Z0-9_]*)>")


def rule_to_regex(rule: str) -> str:
    pattern = ""
    last = 0
    for m in _VARIABLE_RE.finditer(rule):
        pattern += re.escape(rule[last:m.start()])
        converter = m.group(1) or "default"
        name = m.group(2)
        conv_pattern = CONVERTER_PATTERNS.get(converter, CONVERTER_PATTERNS["default"])
        pattern += f"(?P<{name}>{conv_pattern})"
        last = m.end()
    pattern += re.escape(rule[last:])
    return f"^{pattern}$"


def match(
    rule: str,
    rule_methods: tuple[str, ...],
    request_url: str,
    request_method: str,
) -> bool:
    if request_method.upper() not in rule_methods:
        return False
    return bool(re.match(rule_to_regex(rule), request_url))
