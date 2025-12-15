from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class TreeChar:
    symbol: str = ""
    leftSpace: int = 0
    level: int = 0

    def __lt__(self, other: "TreeChar") -> bool:
        return self.level < other.level


@dataclass
class DisplayObject:
    displayBuffer: List[TreeChar] = field(default_factory=list)
    height: int = 0
    width: int = 0

