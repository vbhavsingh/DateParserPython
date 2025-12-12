from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class LocalDateModel:
    original_text: Optional[str] = None
    date_time_string: Optional[str] = None
    con_date_format: Optional[str] = None
    identified_date_format: Optional[str] = None
    start: Optional[int] = None
    end: Optional[int] = None

    def __str__(self) -> str:
        return (
            "LocalDateModel("
            f"original_text={self.original_text}, "
            f"date_time_string={self.date_time_string}, "
            f"con_date_format={self.con_date_format}, "
            f"identified_date_format={self.identified_date_format}, "
            f"start={self.start}, end={self.end})"
        )


@dataclass
class DateElement:
    data: str
    tokenNum: int = 0
    fragments: int = 0
    isAlphaNumeric: bool = False
    aphaNumericType: int = 0
    startPos: int = 0
    endPos: int = 0
    hasAmPm: bool = False
    timeFragment: Optional[str] = None
    dateFragment: Optional[str] = None
    dateTimeSeprator: str = " "

    def getDateFragment(self) -> str:
        if self.timeFragment is None:
            return self.data
        return self.dateFragment or ""

    def __str__(self) -> str:
        return (
            "DateElement("
            f"data={self.data}, tokenNum={self.tokenNum}, fragments={self.fragments}, "
            f"isAlphaNumeric={self.isAlphaNumeric}, aphaNumericType={self.aphaNumericType}, "
            f"startPos={self.startPos}, endPos={self.endPos}, hasAmPm={self.hasAmPm}, "
            f"timeFragment={self.timeFragment}, dateFragment={self.dateFragment}, "
            f"dateTimeSeprator={self.dateTimeSeprator})"
        )

