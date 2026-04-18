"""
Material registry for architectural elements.

``Material`` is a lightweight descriptor (name, colour, thermal properties).
Wall / Beam / Column / Slab elements keep ``material: str | None`` as a
*reference key* — the same key used here — to stay backward-compatible.

Usage::

    from archit_app.elements.material import BUILTIN_MATERIALS, MaterialLibrary

    lib = MaterialLibrary()
    concrete = lib.get("concrete")
    print(concrete.color_hex)   # "#B0B0B0"

    # Register a custom material
    lib.register(Material(name="rammed_earth", color_hex="#C4A882",
                          category=MaterialCategory.OTHER))
"""

from __future__ import annotations

from enum import Enum
from typing import Iterator

from pydantic import BaseModel, ConfigDict, model_validator


class MaterialCategory(str, Enum):
    CONCRETE  = "concrete"
    BRICK     = "brick"
    TIMBER    = "timber"
    GLASS     = "glass"
    STEEL     = "steel"
    GYPSUM    = "gypsum"
    TILE      = "tile"
    STONE     = "stone"
    INSULATION = "insulation"
    METAL     = "metal"
    FABRIC    = "fabric"
    OTHER     = "other"


class Material(BaseModel):
    """
    Descriptor for a building material.

    ``name`` is the lookup key — it must be unique within a ``MaterialLibrary``.
    ``color_hex`` is a CSS hex colour string (``"#RRGGBB"``).
    ``thermal_conductivity_wm`` is λ in W/(m·K); ``None`` if unknown.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    color_hex: str = "#AAAAAA"
    category: MaterialCategory = MaterialCategory.OTHER
    thermal_conductivity_wm: float | None = None   # W/(m·K)
    description: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "Material":
        if not self.name.strip():
            raise ValueError("Material name must not be empty.")
        if not self.color_hex.startswith("#") or len(self.color_hex) not in (4, 7):
            raise ValueError(
                f"color_hex must be a CSS hex string like '#RRGGBB', got {self.color_hex!r}."
            )
        if self.thermal_conductivity_wm is not None and self.thermal_conductivity_wm < 0:
            raise ValueError("thermal_conductivity_wm must be non-negative.")
        return self

    def __repr__(self) -> str:
        return f"Material(name={self.name!r}, category={self.category.value})"


# ---------------------------------------------------------------------------
# Built-in material presets
# ---------------------------------------------------------------------------

BUILTIN_MATERIALS: tuple[Material, ...] = (
    Material(name="concrete",    color_hex="#B0B0B0", category=MaterialCategory.CONCRETE,
             thermal_conductivity_wm=1.7,  description="Standard reinforced concrete"),
    Material(name="brick",       color_hex="#C0633A", category=MaterialCategory.BRICK,
             thermal_conductivity_wm=0.7,  description="Fired clay brick"),
    Material(name="timber",      color_hex="#C8A96E", category=MaterialCategory.TIMBER,
             thermal_conductivity_wm=0.13, description="Structural softwood timber"),
    Material(name="glass",       color_hex="#AED6F1", category=MaterialCategory.GLASS,
             thermal_conductivity_wm=1.0,  description="Clear float glass"),
    Material(name="steel",       color_hex="#808080", category=MaterialCategory.STEEL,
             thermal_conductivity_wm=50.0, description="Structural carbon steel"),
    Material(name="gypsum",      color_hex="#F0EDE0", category=MaterialCategory.GYPSUM,
             thermal_conductivity_wm=0.25, description="Gypsum plasterboard (drywall)"),
    Material(name="plaster",     color_hex="#E8E4D8", category=MaterialCategory.GYPSUM,
             thermal_conductivity_wm=0.4,  description="Wet-applied cement or lime plaster"),
    Material(name="tile",        color_hex="#D4C9C0", category=MaterialCategory.TILE,
             thermal_conductivity_wm=1.3,  description="Ceramic or porcelain floor/wall tile"),
    Material(name="stone",       color_hex="#9E9E8E", category=MaterialCategory.STONE,
             thermal_conductivity_wm=2.3,  description="Natural cut stone (granite/limestone)"),
    Material(name="insulation",  color_hex="#F5E6A3", category=MaterialCategory.INSULATION,
             thermal_conductivity_wm=0.04, description="Mineral wool / glass wool insulation"),
    Material(name="aluminium",   color_hex="#C0C8D0", category=MaterialCategory.METAL,
             thermal_conductivity_wm=160.0, description="Extruded aluminium (curtain wall / frames)"),
    Material(name="carpet",      color_hex="#8B7355", category=MaterialCategory.FABRIC,
             thermal_conductivity_wm=0.06, description="Woven carpet floor finish"),
)


# ---------------------------------------------------------------------------
# MaterialLibrary
# ---------------------------------------------------------------------------

class MaterialLibrary:
    """
    Registry of ``Material`` objects keyed by name.

    Constructed pre-loaded with ``BUILTIN_MATERIALS``. Additional materials
    can be registered at runtime.
    """

    def __init__(self, *, include_builtins: bool = True) -> None:
        self._store: dict[str, Material] = {}
        if include_builtins:
            for m in BUILTIN_MATERIALS:
                self._store[m.name] = m

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def register(self, material: Material) -> None:
        """Add or replace a material in the library."""
        self._store[material.name] = material

    def unregister(self, name: str) -> None:
        """Remove a material by name. Raises KeyError if not found."""
        if name not in self._store:
            raise KeyError(f"Material {name!r} is not registered.")
        del self._store[name]

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, name: str) -> Material:
        """Return the material with ``name``. Raises KeyError if not found."""
        try:
            return self._store[name]
        except KeyError:
            raise KeyError(f"Material {name!r} is not registered.") from None

    def get_or_none(self, name: str) -> Material | None:
        """Return the material with ``name``, or None if not registered."""
        return self._store.get(name)

    def all(self) -> list[Material]:
        """Return all registered materials sorted by name."""
        return sorted(self._store.values(), key=lambda m: m.name)

    def by_category(self, category: MaterialCategory) -> list[Material]:
        """Return all materials in ``category``, sorted by name."""
        return sorted(
            (m for m in self._store.values() if m.category == category),
            key=lambda m: m.name,
        )

    def names(self) -> list[str]:
        """Return all registered material names sorted alphabetically."""
        return sorted(self._store.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._store

    def __len__(self) -> int:
        return len(self._store)

    def __iter__(self) -> Iterator[Material]:
        return iter(self.all())

    def __repr__(self) -> str:
        return f"MaterialLibrary({len(self._store)} materials)"


# ---------------------------------------------------------------------------
# Module-level default library (singleton for convenience)
# ---------------------------------------------------------------------------

#: A module-level default ``MaterialLibrary`` pre-loaded with the 12 builtin
#: materials. Import and use directly, or instantiate your own library.
default_library: MaterialLibrary = MaterialLibrary()
