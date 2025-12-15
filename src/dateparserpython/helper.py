from __future__ import annotations

import random
from typing import List

try:
    from . import dictionary as Dictionary
except ImportError:  # pragma: no cover - fallback for direct module execution
    from dateparserpython import dictionary as Dictionary


def isDateLieral(token: str) -> int:
    """
    Port of Helper.isDateLieral from Java. Returns Dictionary constants that
    describe the literal type for quick scanning.
    """

    s = token.lower()
    if len(token) > 9:
        return Dictionary.NOT_DATE_LITERAL
    if len(s) <= 2 and isDigit(s):
        return Dictionary.DIGIT_LITERAL
    if len(s) == 3 and isDigit(s):
        return Dictionary.THREE_DIGIT_LITERAL
    if len(s) == 4 and isDigit(s):
        return Dictionary.FOUR_DIGIT_LITERAL
    if len(s) <= 2:
        return Dictionary.NOT_DATE_LITERAL
    if any(char in s for char in "kqxz"):
        return Dictionary.NOT_DATE_LITERAL
    if isWeekDayLiteral(s):
        return Dictionary.WEEKDAY_LITERAL
    if isMonthLiteral(s):
        return Dictionary.MONTH_LITERAL
    return Dictionary.NOT_DATE_LITERAL


def isMonthLiteral(s: str) -> bool:
    if "w" in s:
        return False
    if len(s) == 3 and ("h" in s or "i" in s):
        return False
    if s in Dictionary.MONTH_SHORT:
        return True
    if s in Dictionary.MONTH_FULL:
        return True
    return False


def hasFullMonthLiteral(s: str) -> bool:
    s = s.lower()
    return any(month in s for month in Dictionary.MONTH_FULL)


def isWeekDayLiteral(s: str) -> bool:
    if any(char in s for char in "bcgjlpv"):
        return False
    if s in Dictionary.WEEKDAY_SHORT:
        return True
    if s in Dictionary.WEEKDAY_FULL:
        return True
    return False


def isDigit(value) -> bool:
    s = str(value)
    if not s:
        return False
    return all("0" <= c <= "9" for c in s)


def isDelimeter(c: str) -> bool:
    return c in "\\/ -.,:_"


def isTimeSeprator(c: str) -> bool:
    return c in " _-T"


def testDataForDateFormats() -> List[str]:
    date_patterns = []
    for pattern in Dictionary.PATTERN:
        test_data = "".join(getTestDataForChar(char) for char in pattern)
        date_patterns.append(test_data)
    time_patterns = []
    for pattern in Dictionary.TIME_PATTERN:
        test_data = "".join(getTestDataForChar(char) for char in pattern)
        time_patterns.append(test_data)
    combined = []
    for date_fragment in date_patterns:
        for time_fragment in time_patterns:
            combined.append(f"{date_fragment} {time_fragment}")
    date_patterns.extend(combined)
    return date_patterns


def getTestDataForChar(c: str) -> str:
    if c == "D":
        return str(random.randint(0, 9))
    if c == "*":
        return getTestCaseDelimeter(random.randint(1, 6))
    if c == "M":
        return getTestMonth(random.randint(1, 24))
    return c


def getTestCaseDelimeter(i: int) -> str:
    mapping = {
        1: "\\",
        2: "/",
        3: "-",
        4: " ",
        5: ".",
        6: ",",
    }
    return mapping.get(i, "~")


def getTestMonth(i: int) -> str:
    months = {
        1: "january",
        2: "february",
        3: "march",
        4: "april",
        5: "may",
        6: "june",
        7: "july",
        8: "august",
        9: "september",
        10: "october",
        11: "november",
        12: "december",
        13: "jan",
        14: "feb",
        15: "mar",
        16: "apr",
        17: "may",
        18: "jun",
        19: "jul",
        20: "aug",
        21: "sep",
        22: "oct",
        23: "nov",
        24: "dec",
    }
    return months.get(i, "")


def isFullMonth(s: str) -> bool:
    s = s.lower()
    return any(month in s for month in Dictionary.MONTH_FULL)


def getDaysinMonth(month: int, year: int) -> int:
    if month > 12:
        return -1
    if month == 2:
        if month % 4 == 0:
            return 29
        return 28
    if month == 8:
        return 31
    if month < 8 and month % 2 == 1:
        return 31
    if month < 8 and month % 2 == 0:
        return 30
    if month % 2 == 1:
        return 30
    return 31
