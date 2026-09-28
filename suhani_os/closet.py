"""The closet and the gift rules: object-oriented design with inheritance and polymorphism.

Class tree:
    Item
    ├── Garment          (has a fabric blend; must be all natural fibers)
    │   ├── Dress
    │   └── Top
    ├── Stationery       (lasting, so it makes a great main gift)
    ├── Food             (never the main gift)
    └── Flowers          (never the main gift)

Each subclass overrides only what makes it different; `Gift` never checks types
directly. It asks each item `is_lasting()` and calls `inspect()`, and lets
polymorphism do the rest.
"""
from __future__ import annotations

from .errors import NotAGiftError, PolyesterError

NATURAL_FIBERS = frozenset({"cotton", "linen", "wool", "silk"})


class Item:
    lasting = True  # most things you can keep for years

    def __init__(self, name: str, brand: str, price: float) -> None:
        if price < 0:
            raise ValueError("price can't be negative")
        self.name = name
        self.brand = brand
        self.price = price

    def is_lasting(self) -> bool:
        return self.lasting

    def inspect(self) -> None:
        """Raise if the item breaks a rule. Plain items have nothing to check."""

    def __str__(self) -> str:
        return f"{self.name} by {self.brand} (${self.price:,.2f})"

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name!r}, {self.brand!r}, {self.price!r})"


class Garment(Item):
    def __init__(self, name: str, brand: str, price: float, fabrics: dict) -> None:
        super().__init__(name, brand, price)
        fabrics = {fiber.lower().strip(): pct for fiber, pct in fabrics.items()}
        if abs(sum(fabrics.values()) - 100) > 0.01:
            raise ValueError(f"{name}: fabric blend adds up to {sum(fabrics.values())}%, not 100%")
        self.fabrics = fabrics

    def synthetic_fibers(self) -> set:
        """Set difference: everything in the blend that isn't on the whitelist."""
        return set(self.fabrics) - NATURAL_FIBERS

    def inspect(self) -> None:
        offenders = self.synthetic_fibers()
        if offenders:
            raise PolyesterError(self.name, list(offenders))

    def label(self) -> str:
        """Care-label style: largest fiber first, e.g. '70% linen, 30% cotton'."""
        parts = sorted(self.fabrics.items(), key=lambda kv: (-kv[1], kv[0]))
        return ", ".join(f"{pct:g}% {fiber}" for fiber, pct in parts)


class Dress(Garment):
    pass


class Top(Garment):
    pass


class Stationery(Item):
    pass


class Food(Item):
    lasting = False


class Flowers(Item):
    lasting = False


class Gift:
    """One main gift plus any number of extras (food and flowers are perfect extras)."""

    def __init__(self, main: Item, *extras: Item) -> None:
        self.main = main
        self.extras = list(extras)

    def approve(self) -> str:
        if not self.main.is_lasting():
            raise NotAGiftError(
                f"{self.main.name} can come along, but it can't be the main gift. "
                "The main gift should be something she keeps."
            )
        for item in [self.main, *self.extras]:
            item.inspect()
        total = self.main.price + sum(e.price for e in self.extras)
        extras = f" with {len(self.extras)} extra{'s' * (len(self.extras) != 1)}" if self.extras else ""
        return f"Approved ✦ {self.main.name}{extras}, ${total:,.2f} total"


def shop(items: list) -> tuple:
    """Split a shopping cart into (keep, put back), with the reason for each put-back."""
    keep, put_back = [], []
    for item in items:
        try:
            item.inspect()
        except PolyesterError as err:
            put_back.append((item, str(err)))
        else:
            keep.append(item)
    return keep, put_back
