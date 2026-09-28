"""The bookshelf: a self-balancing AVL tree, plus sorting and searching from scratch.

Why a balanced tree? If books go in alphabetically (the way most shelves get filled),
a plain binary search tree turns into a linked list and every lookup costs O(n).
AVL rotations keep the height under about 1.44 * log2(n), so insert, search and
delete stay O(log n) no matter what order the books arrive in.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

DATA = Path(__file__).parent / "data" / "bookshelf.csv"


@dataclass(frozen=True)
class Book:
    title: str
    author: str
    shelf: str

    @property
    def sort_title(self) -> str:
        """Librarian rule: ignore a leading 'The', 'A' or 'An' when alphabetizing."""
        lowered = self.title.lower()
        for article in ("the ", "a ", "an "):
            if lowered.startswith(article):
                return lowered[len(article):]
        return lowered

    @property
    def author_last(self) -> str:
        return self.author.split()[-1].lower()


def load_books(path: Path = DATA) -> list:
    with open(path, newline="", encoding="utf-8") as f:
        return [Book(row["title"], row["author"], row["shelf"]) for row in csv.DictReader(f)]


# ---------------------------------------------------------------- AVL tree

class _Node:
    __slots__ = ("key", "book", "left", "right", "height")

    def __init__(self, key: str, book: Book) -> None:
        self.key = key
        self.book = book
        self.left = None
        self.right = None
        self.height = 1


def _h(node) -> int:
    return node.height if node else 0


def _update(node: _Node) -> None:
    node.height = 1 + max(_h(node.left), _h(node.right))


def _balance(node) -> int:
    return _h(node.left) - _h(node.right) if node else 0


def _rotate_right(y: _Node) -> _Node:
    x = y.left
    y.left, x.right = x.right, y
    _update(y)
    _update(x)
    return x


def _rotate_left(x: _Node) -> _Node:
    y = x.right
    x.right, y.left = y.left, x
    _update(x)
    _update(y)
    return y


def _rebalance(node: _Node) -> _Node:
    _update(node)
    bal = _balance(node)
    if bal > 1:                                  # left heavy
        if _balance(node.left) < 0:              # left-right case
            node.left = _rotate_left(node.left)
        return _rotate_right(node)
    if bal < -1:                                 # right heavy
        if _balance(node.right) > 0:             # right-left case
            node.right = _rotate_right(node.right)
        return _rotate_left(node)
    return node


class Bookshelf:
    """An AVL tree of books keyed by their shelf title (leading 'The' ignored)."""

    def __init__(self, books=()) -> None:
        self._root = None
        self._size = 0
        for book in books:
            self.add(book)

    def add(self, book: Book) -> None:
        self._root = self._insert(self._root, book.sort_title, book)

    def _insert(self, node, key: str, book: Book) -> _Node:
        if node is None:
            self._size += 1
            return _Node(key, book)
        if key < node.key:
            node.left = self._insert(node.left, key, book)
        elif key > node.key:
            node.right = self._insert(node.right, key, book)
        else:
            node.book = book  # same title: replace (a new edition), don't duplicate
            return node
        return _rebalance(node)

    def remove(self, title: str) -> None:
        key = Book(title, "", "").sort_title
        if key not in self:
            raise KeyError(title)
        self._root = self._delete(self._root, key)
        self._size -= 1

    def _delete(self, node: _Node, key: str):
        if key < node.key:
            node.left = self._delete(node.left, key)
        elif key > node.key:
            node.right = self._delete(node.right, key)
        else:
            if node.left is None or node.right is None:
                return node.left or node.right
            # two children: borrow the in-order successor (smallest key on the right)
            succ = node.right
            while succ.left:
                succ = succ.left
            node.key, node.book = succ.key, succ.book
            node.right = self._delete(node.right, succ.key)
        return _rebalance(node)

    def find(self, title: str):
        """Iterative binary search down the tree: O(log n)."""
        key = Book(title, "", "").sort_title
        node = self._root
        while node:
            if key == node.key:
                return node.book
            node = node.left if key < node.key else node.right
        return None

    def __contains__(self, key: str) -> bool:
        node = self._root
        while node:
            if key == node.key:
                return True
            node = node.left if key < node.key else node.right
        return False

    def __len__(self) -> int:
        return self._size

    def __iter__(self):
        """In-order traversal (recursive), which visits books in alphabetical order."""
        yield from self._in_order(self._root)

    def _in_order(self, node):
        if node:
            yield from self._in_order(node.left)
            yield node.book
            yield from self._in_order(node.right)

    @property
    def height(self) -> int:
        return _h(self._root)

    def between(self, low: str, high: str) -> list:
        """Range query: every title from `low` to `high`, skipping subtrees that can't match."""
        out = []

        def walk(node):
            if node is None:
                return
            if low < node.key:
                walk(node.left)
            if low <= node.key <= high:
                out.append(node.book)
            if node.key < high:
                walk(node.right)

        walk(self._root)
        return out


# ---------------------------------------------------------------- sorting and searching

def merge_sort(items: list, key=lambda x: x) -> list:
    """Divide and conquer, O(n log n) always, and stable (equal keys keep their order)."""
    if len(items) <= 1:
        return list(items)
    mid = len(items) // 2
    left, right = merge_sort(items[:mid], key), merge_sort(items[mid:], key)
    merged, i, j = [], 0, 0
    while i < len(left) and j < len(right):
        if key(right[j]) < key(left[i]):
            merged.append(right[j])
            j += 1
        else:
            merged.append(left[i])
            i += 1
    return merged + left[i:] + right[j:]


def quicksort(items: list, key=lambda x: x) -> list:
    """Average O(n log n). Median-of-three pivot avoids the O(n^2) trap on already-sorted input."""
    if len(items) <= 1:
        return list(items)
    first, middle, last = items[0], items[len(items) // 2], items[-1]
    pivot = key(sorted((first, middle, last), key=key)[1])
    less = [x for x in items if key(x) < pivot]
    equal = [x for x in items if key(x) == pivot]
    more = [x for x in items if key(x) > pivot]
    return quicksort(less, key) + equal + quicksort(more, key)


def binary_search(sorted_items: list, target, key=lambda x: x) -> int:
    """Index of target in a sorted list, or -1. O(log n)."""
    lo, hi = 0, len(sorted_items) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        k = key(sorted_items[mid])
        if k == target:
            return mid
        if k < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1


def shelves(books: list) -> dict:
    """Group books by shelf: a dict of lists, each alphabetized by author."""
    grouped = {}
    for book in books:
        grouped.setdefault(book.shelf, []).append(book)
    return {shelf: merge_sort(group, key=lambda b: (b.author_last, b.sort_title))
            for shelf, group in grouped.items()}
