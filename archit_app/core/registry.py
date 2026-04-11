"""
Plugin registry for extensible element types, exporters, importers, etc.

Usage — third-party plugin:

    from archit_app.core.registry import register

    @register("wall_type", "double_skin")
    class DoubleSkinWall(Wall):
        ...

    @register("exporter", "revit_rvt")
    class RevitExporter(BaseExporter):
        ...
"""

from __future__ import annotations

from collections import defaultdict

_registry: dict[str, dict[str, type]] = defaultdict(dict)


def register(category: str, name: str):
    """
    Class decorator that registers a class under a category/name pair.

    Raises ValueError if the name is already registered under the category,
    preventing silent plugin conflicts.
    """

    def decorator(cls: type) -> type:
        if name in _registry[category]:
            raise ValueError(
                f"'{name}' is already registered under category '{category}'. "
                f"Existing: {_registry[category][name]!r}. New: {cls!r}."
            )
        _registry[category][name] = cls
        return cls

    return decorator


def get(category: str, name: str) -> type:
    """Retrieve a registered class by category and name."""
    try:
        return _registry[category][name]
    except KeyError:
        available = list(_registry.get(category, {}).keys())
        raise KeyError(
            f"No '{name}' registered under category '{category}'. "
            f"Available: {available}"
        )


def list_registered(category: str) -> list[str]:
    """List all registered names under a category."""
    return list(_registry.get(category, {}).keys())


def get_all(category: str) -> dict[str, type]:
    """Get all registered classes under a category."""
    return dict(_registry.get(category, {}))


def _clear(category: str | None = None) -> None:
    """
    Clear the registry. For use in tests only — never call in production code.
    """
    global _registry
    if category is None:
        _registry = defaultdict(dict)
    elif category in _registry:
        del _registry[category]
