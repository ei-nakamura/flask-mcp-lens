from __future__ import annotations

import ast


class AliasMap:
    """Tracks Flask import aliases within a single file."""

    def __init__(self) -> None:
        # local_name → canonical Flask class name (e.g. "BP" → "Blueprint")
        self._aliases: dict[str, str] = {}
        # module-level import aliases (e.g. "import flask as fl" → "fl")
        self._module_aliases: set[str] = set()

    @classmethod
    def build(cls, tree: ast.Module) -> "AliasMap":
        obj = cls()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "flask" or module.startswith("flask."):
                    for alias in node.names:
                        local = alias.asname if alias.asname else alias.name
                        obj._aliases[local] = alias.name
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "flask" or alias.name.startswith("flask."):
                        local = alias.asname if alias.asname else alias.name
                        obj._module_aliases.add(local)
        return obj

    def resolve(self, name: str) -> str:
        """Resolve a local name to its canonical Flask class name.

        Examples:
            "BP"              → "Blueprint"   (from flask import Blueprint as BP)
            "Blueprint"       → "Blueprint"   (from flask import Blueprint)
            "flask.Blueprint" → "Blueprint"   (import flask)
        Returns name unchanged if unresolvable.
        """
        if name in self._aliases:
            return self._aliases[name]
        if "." in name:
            prefix, _, attr = name.partition(".")
            if prefix in self._module_aliases:
                return attr
        return name
