from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PredictionModelNode:
    """
    Python equivalent of the Java PredictionModelNode used by the parser's
    dictionary tries.
    """

    charcter: str = "\x00"
    level: int = 0
    is_digit: bool = False
    explict_date_fragment: bool = False
    parent: Optional["PredictionModelNode"] = None
    childern: List["PredictionModelNode"] = field(default_factory=list)

    def get_child(self, char: str) -> Optional["PredictionModelNode"]:
        for child in self.childern:
            if child.charcter == char:
                return child
        return None

    def add_child(self, child: "PredictionModelNode") -> None:
        child.level = self.level + 1
        child.parent = self
        self.childern.append(child)

    def has_childern(self) -> bool:
        return bool(self.childern)

    def children_count(self) -> int:
        return len(self.childern)

