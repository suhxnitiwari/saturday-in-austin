"""The bakery: a linked list, a stack and a queue, each built from scratch.

  Recipe steps  -> singly linked list  (insert a step in the middle without shifting everything)
  Undo button   -> stack               (last change in, first change undone)
  Cake orders   -> queue               (first order in, first cake out)

Cooking stays aspirational. Baking is where she shines.
"""
from __future__ import annotations

from fractions import Fraction


# ---------------------------------------------------------------- linked list

class _Step:
    __slots__ = ("text", "next")

    def __init__(self, text: str, nxt=None) -> None:
        self.text = text
        self.next = nxt


class StepList:
    """Singly linked list of recipe steps with a tail pointer, so append is O(1)."""

    def __init__(self, steps=()) -> None:
        self._head = self._tail = None
        self._size = 0
        for s in steps:
            self.append(s)

    def append(self, text: str) -> None:
        node = _Step(text)
        if self._tail:
            self._tail.next = node
        else:
            self._head = node
        self._tail = node
        self._size += 1

    def insert(self, index: int, text: str) -> None:
        """Insert before position `index` (0 = new first step)."""
        if not 0 <= index <= self._size:
            raise IndexError(f"step {index} is out of range")
        if index == self._size:
            self.append(text)
            return
        if index == 0:
            self._head = _Step(text, self._head)
        else:
            prev = self._node_at(index - 1)
            prev.next = _Step(text, prev.next)
        self._size += 1

    def pop(self, index: int) -> str:
        """Remove and return the step at `index`."""
        if not 0 <= index < self._size:
            raise IndexError(f"step {index} is out of range")
        if index == 0:
            node = self._head
            self._head = node.next
            if node is self._tail:
                self._tail = None
        else:
            prev = self._node_at(index - 1)
            node = prev.next
            prev.next = node.next
            if node is self._tail:
                self._tail = prev
        self._size -= 1
        return node.text

    def reverse(self) -> None:
        """Reverse in place by re-pointing every link: O(n) time, O(1) extra space."""
        prev, cur = None, self._head
        self._tail = cur
        while cur:
            cur.next, prev, cur = prev, cur, cur.next
        self._head = prev

    def _node_at(self, index: int) -> _Step:
        node = self._head
        for _ in range(index):
            node = node.next
        return node

    def __iter__(self):
        node = self._head
        while node:
            yield node.text
            node = node.next

    def __len__(self) -> int:
        return self._size

    def __getitem__(self, index: int) -> str:
        if not 0 <= index < self._size:
            raise IndexError(index)
        return self._node_at(index).text


# ---------------------------------------------------------------- stack and queue

class Stack:
    """Last in, first out. Backed by a Python list; push and pop at the end are O(1)."""

    def __init__(self) -> None:
        self._items = []

    def push(self, item) -> None:
        self._items.append(item)

    def pop(self):
        if self.is_empty():
            raise IndexError("nothing to undo")
        return self._items.pop()

    def peek(self):
        if self.is_empty():
            raise IndexError("the stack is empty")
        return self._items[-1]

    def is_empty(self) -> bool:
        return not self._items

    def __len__(self) -> int:
        return len(self._items)


class Queue:
    """First in, first out, built on linked nodes so both enqueue and dequeue are O(1).

    (A plain list would make dequeue O(n), because list.pop(0) shifts every element.)
    """

    def __init__(self) -> None:
        self._front = self._back = None
        self._size = 0

    def enqueue(self, item) -> None:
        node = _Step(item)
        if self._back:
            self._back.next = node
        else:
            self._front = node
        self._back = node
        self._size += 1

    def dequeue(self):
        if self._front is None:
            raise IndexError("no orders waiting")
        node = self._front
        self._front = node.next
        if self._front is None:
            self._back = None
        self._size -= 1
        return node.text

    def peek(self):
        if self._front is None:
            raise IndexError("no orders waiting")
        return self._front.text

    def __len__(self) -> int:
        return self._size


# ---------------------------------------------------------------- recipes

class Recipe:
    def __init__(self, name: str, serves: int, ingredients: dict, steps=()) -> None:
        self.name = name
        self.serves = serves
        # quantities are Fractions so "3/4 cup" scales exactly (floats would drift: 0.1 + 0.2 != 0.3)
        self.ingredients = {k: (Fraction(q), unit) for k, (q, unit) in ingredients.items()}
        self.steps = StepList(steps)
        self._history = Stack()

    def scaled(self, serves: int) -> "Recipe":
        factor = Fraction(serves, self.serves)
        return Recipe(self.name, serves,
                      {k: (q * factor, unit) for k, (q, unit) in self.ingredients.items()},
                      list(self.steps))

    # every edit records how to reverse itself, so undo is just "pop and apply"
    def add_step(self, text: str, index=None) -> None:
        index = len(self.steps) if index is None else index
        self.steps.insert(index, text)
        self._history.push(("remove", index, None))

    def remove_step(self, index: int) -> str:
        text = self.steps.pop(index)
        self._history.push(("insert", index, text))
        return text

    def undo(self) -> None:
        action, index, text = self._history.pop()
        if action == "remove":
            self.steps.pop(index)
        else:
            self.steps.insert(index, text)

    def card(self) -> str:
        """A printable recipe card with kitchen-friendly fractions like '1 1/2 cups'."""
        lines = [f"✦ {self.name} (serves {self.serves})", ""]
        width = max(len(k) for k in self.ingredients)
        for name, (qty, unit) in self.ingredients.items():
            unit = unit + "s" if unit == "cup" and qty > 1 else unit
            lines.append(f"  {name:<{width}}  {pretty_amount(qty)} {unit}".rstrip())
        lines.append("")
        lines += [f"  {i}. {step}" for i, step in enumerate(self.steps, start=1)]
        return "\n".join(lines)


def pretty_amount(q: Fraction) -> str:
    """Fraction(3, 2) -> '1 1/2', Fraction(1, 4) -> '1/4', Fraction(2) -> '2'."""
    whole, rem = divmod(q.numerator, q.denominator)
    if rem == 0:
        return str(whole)
    frac = f"{rem}/{q.denominator}"
    return f"{whole} {frac}" if whole else frac


class Kitchen:
    """Takes cake orders in the order they come in and bakes them one at a time."""

    def __init__(self) -> None:
        self.orders = Queue()
        self.baked = []

    def order(self, cake: str, for_whom: str) -> int:
        self.orders.enqueue((cake, for_whom))
        return len(self.orders)  # place in line

    def bake_next(self) -> str:
        cake, for_whom = self.orders.dequeue()
        self.baked.append(cake)
        return f"{cake} for {for_whom}, fresh out of the oven ✦"

    @staticmethod
    def make_toast() -> str:
        return "Burnt. Cooking will become a hobby once the toast stops fighting back."


BANANA_BREAD = Recipe(
    "Chocolate Chip Banana Bread", serves=8,
    ingredients={
        "ripe bananas": (3, ""),
        "flour": (Fraction(3, 2), "cup"),
        "melted butter": (Fraction(1, 3), "cup"),
        "sugar": (Fraction(3, 4), "cup"),
        "eggs": (1, ""),
        "vanilla": (1, "tsp"),
        "baking soda": (1, "tsp"),
        "chocolate chips": (Fraction(2, 3), "cup"),
    },
    steps=[
        "Mash the bananas in a big bowl.",
        "Stir in the melted butter, then the sugar, eggs and vanilla.",
        "Fold in the flour and baking soda until just combined.",
        "Add the chocolate chips (be generous).",
        "Bake at 350°F for about 60 minutes.",
    ],
)

CAKES_SHE_HAS_MADE = ["Lego cake", "Solar system cake", "Rainbow cake"]
