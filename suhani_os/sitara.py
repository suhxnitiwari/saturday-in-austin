"""Mini Sitara: a tiny offline version of the fairy guide on suhanitiwari.com.

Strings, dictionaries, sets and file I/O: questions are cleaned up, split into words,
and matched against the keywords for each topic in a JSON file. The topic sharing the
most words wins. Same fairy-dust rule as the real Sitara: 25 questions per visit.
"""
from __future__ import annotations

import json
import string
from pathlib import Path

from .errors import HorrorError, OutOfFairyDust

DATA = Path(__file__).parent / "data" / "sitara.json"
DUST_LIMIT = 25
_STRIP = str.maketrans("", "", string.punctuation.replace("'", ""))


def tokenize(text: str) -> set:
    """'What's her FAVORITE color?!' -> {"what's", 'her', 'favorite', 'color'}"""
    return set(text.lower().translate(_STRIP).split())


class Sitara:
    def __init__(self, path: Path = DATA) -> None:
        with open(path, encoding="utf-8") as f:
            self.topics = json.load(f)
        self.asked = 0

    def best_topic(self, question: str):
        words = tokenize(question)
        scores = {name: len(words & set(t["keywords"])) for name, t in self.topics.items()}
        name, score = max(scores.items(), key=lambda kv: (kv[1], kv[0]))
        return name if score else None

    def ask(self, question: str) -> str:
        if self.asked >= DUST_LIMIT:
            raise OutOfFairyDust("I'm all out of fairy dust for today ✦ Come back later.")
        self.asked += 1
        if "horror" in tokenize(question):
            raise HorrorError("Horror? Absolutely not. Ask me about rom-coms instead.")
        topic = self.best_topic(question)
        answer = self.topics[topic]["answer"] if topic else (
            "That one's not in my notes yet ✦ Try asking about her books, Läderach, or Austin.")
        if self.asked == DUST_LIMIT - 1:
            answer += "\n✦ Psst: last question!"
        return answer
