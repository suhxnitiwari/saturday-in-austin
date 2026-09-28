"""The Läderach counter: a hash map and a max-heap built from scratch, then greedy vs.
dynamic programming to pack the best possible box.

The scenario: FrischSchoggi comes in giant slabs, and the counter breaks off pieces
by weight. You have a gram limit. Which pieces make the best box?
Florentine, Salted Caramel and Hazelnut are the confirmed favorites.
"""
from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------- hash map

class FlavorMap:
    """A hash table with separate chaining, written out by hand.

    Each bucket is a list of (key, value) pairs. When the table gets more than 75% full
    it doubles and rehashes, which keeps chains short so get/put stay O(1) on average.
    """

    LOAD_FACTOR = 0.75

    def __init__(self, capacity: int = 8) -> None:
        self._buckets = [[] for _ in range(capacity)]
        self._size = 0

    @staticmethod
    def _hash(key: str) -> int:
        """Polynomial rolling hash (the same idea as Java's String.hashCode)."""
        h = 0
        for ch in key.lower():
            h = (h * 31 + ord(ch)) & 0xFFFFFFFF
        return h

    def _bucket(self, key: str) -> list:
        return self._buckets[self._hash(key) % len(self._buckets)]

    def put(self, key: str, value) -> None:
        bucket = self._bucket(key)
        for i, (k, _) in enumerate(bucket):
            if k.lower() == key.lower():
                bucket[i] = (k, value)
                return
        bucket.append((key, value))
        self._size += 1
        if self._size / len(self._buckets) > self.LOAD_FACTOR:
            self._resize()

    def get(self, key: str, default=None):
        for k, v in self._bucket(key):
            if k.lower() == key.lower():
                return v
        return default

    def remove(self, key: str) -> None:
        bucket = self._bucket(key)
        for i, (k, _) in enumerate(bucket):
            if k.lower() == key.lower():
                del bucket[i]
                self._size -= 1
                return
        raise KeyError(key)

    def _resize(self) -> None:
        old = [pair for bucket in self._buckets for pair in bucket]
        self._buckets = [[] for _ in range(len(self._buckets) * 2)]
        self._size = 0
        for k, v in old:
            self.put(k, v)

    def __contains__(self, key: str) -> bool:
        return self.get(key, _MISSING) is not _MISSING

    def __len__(self) -> int:
        return self._size

    def keys(self) -> list:
        return [k for bucket in self._buckets for k, _ in bucket]

    @property
    def capacity(self) -> int:
        return len(self._buckets)


_MISSING = object()


# ---------------------------------------------------------------- max-heap

class MaxHeap:
    """A binary max-heap stored in a plain list: children of index i live at 2i+1 and 2i+2.

    push and pop are O(log n); peek is O(1); heapify builds from a list in O(n).
    """

    def __init__(self, items=(), key=lambda x: x) -> None:
        self._key = key
        self._data = list(items)
        for i in reversed(range(len(self._data) // 2)):
            self._sift_down(i)

    def push(self, item) -> None:
        self._data.append(item)
        self._sift_up(len(self._data) - 1)

    def pop(self):
        if not self._data:
            raise IndexError("pop from an empty heap")
        top = self._data[0]
        last = self._data.pop()
        if self._data:
            self._data[0] = last
            self._sift_down(0)
        return top

    def peek(self):
        if not self._data:
            raise IndexError("peek at an empty heap")
        return self._data[0]

    def __len__(self) -> int:
        return len(self._data)

    def _sift_up(self, i: int) -> None:
        k = self._key
        while i > 0:
            parent = (i - 1) // 2
            if k(self._data[i]) <= k(self._data[parent]):
                break
            self._data[i], self._data[parent] = self._data[parent], self._data[i]
            i = parent

    def _sift_down(self, i: int) -> None:
        k, n = self._key, len(self._data)
        while True:
            largest, left, right = i, 2 * i + 1, 2 * i + 2
            if left < n and k(self._data[left]) > k(self._data[largest]):
                largest = left
            if right < n and k(self._data[right]) > k(self._data[largest]):
                largest = right
            if largest == i:
                return
            self._data[i], self._data[largest] = self._data[largest], self._data[i]
            i = largest


# ---------------------------------------------------------------- packing the box

@dataclass(frozen=True)
class Piece:
    flavor: str
    grams: int
    love: int  # how happy this piece makes her, 1 to 10

    @property
    def love_per_gram(self) -> float:
        return self.love / self.grams


FAVORITES = ("Florentine", "Salted Caramel", "Hazelnut")

# Today's counter (piece sizes and love scores are sample data for the demo)
COUNTER = [
    Piece("Florentine", 120, 10),
    Piece("Salted Caramel", 110, 10),
    Piece("Hazelnut", 100, 10),
    Piece("Dark Almond", 60, 5),
    Piece("Milk Almond", 70, 5),
    Piece("White Raspberry", 50, 4),
    Piece("Pistachio", 90, 6),
]


def greedy_box(pieces: list, limit: int) -> tuple:
    """Take the best love-per-gram piece that still fits, again and again (uses the heap).

    Fast, O(n log n), and usually good, but not always optimal.
    """
    heap = MaxHeap(pieces, key=lambda p: p.love_per_gram)
    box, grams = [], 0
    while heap:
        p = heap.pop()
        if grams + p.grams <= limit:
            box.append(p)
            grams += p.grams
    return sum(p.love for p in box), box


def best_box(pieces: list, limit: int) -> tuple:
    """0/1 knapsack with dynamic programming: the provably best box, O(n * limit).

    best[i][g] = the most love using only the first i pieces within g grams.
    """
    n = len(pieces)
    best = [[0] * (limit + 1) for _ in range(n + 1)]
    for i, p in enumerate(pieces, start=1):
        for g in range(limit + 1):
            best[i][g] = best[i - 1][g]
            if p.grams <= g:
                best[i][g] = max(best[i][g], best[i - 1][g - p.grams] + p.love)

    # trace back through the table to see which pieces were chosen
    box, g = [], limit
    for i in range(n, 0, -1):
        if best[i][g] != best[i - 1][g]:
            box.append(pieces[i - 1])
            g -= pieces[i - 1].grams
    return best[n][limit], box[::-1]


def build_menu(pieces: list = COUNTER) -> FlavorMap:
    menu = FlavorMap()
    for p in pieces:
        menu.put(p.flavor, p)
    return menu
