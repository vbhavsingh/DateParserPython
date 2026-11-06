"""Generated tests covering every date and time pattern the parser knows.

Cases are built from dictionary.PATTERN and dictionary.TIME_PATTERN, so each
pattern gets exercised with every supported delimiter, field order, padding,
month-name spelling, time format, date/time separator, meridiem and
surrounding context. Expected values come from datetime, not the parser.

Run with:  python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import re
import sys
import unittest
from dataclasses import dataclass
from datetime import date, datetime, time
from itertools import product
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dateparserpython import Parser  # noqa: E402
from dateparserpython import dictionary as Dictionary  # noqa: E402

MONTHS_FULL = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
MONTHS_SHORT = [m[:3] for m in MONTHS_FULL]
WEEKDAYS_FULL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Single delimiters accepted between date fields ("*" in PATTERN).
# Both separators of a numeric date must be the same one of these (see Parser._isPlausible).
NUMERIC_DELIMITERS = ["/", "-", ".", " ", "\\"]
ALPHA_DELIMITERS = [" ", "-", ".", "/", ","]
# Two-character delimiters ("**" in PATTERN), e.g. "Dec 12, 2025" or "12 Dec. 2025".
ALPHA_DOUBLE_DELIMITERS = [", ", ". "]

DATE_TIME_SEPARATORS = [" ", "T", "_", "-"]

# Every date with a one- and two-digit day/month, the 12/13 boundary and each month's last day.
SAMPLE_DAYS = (1, 5, 9, 10, 12, 13, 28)
# 4-digit years; two-digit renders cover both sides of 31 and of the 1969/2068 pivot.
SAMPLE_YEARS = (2024, 1999, 2005, 1970, 2068)


@dataclass(frozen=True)
class Case:
    text: str
    value: str
    fmt: str


def last_day(year: int, month: int) -> int:
    nxt = date(year + month // 12, month % 12 + 1, 1)
    return (nxt - date(year, month, 1)).days


def sample_dates(years: Sequence[int] = SAMPLE_YEARS) -> Iterator[date]:
    for year, month in product(years, range(1, 13)):
        for day in sorted(set(SAMPLE_DAYS + (last_day(year, month),))):
            yield date(year, month, day)


def split_pattern(pattern: str) -> Tuple[List[str], List[str]]:
    """'DD*M**DDDD' -> (['DD', 'M', 'DDDD'], ['*', '**'])."""
    parts = re.findall(r"D+|M|\*+", pattern)
    return [p for p in parts if not p.startswith("*")], [p for p in parts if p.startswith("*")]


def is_full_month(name: str) -> bool:
    return name.lower() in {m.lower() for m in MONTHS_FULL}


def month_format(name: str) -> str:
    return "MMMMM" if is_full_month(name) else "MMM"


def render_number(value: int, slot: str) -> Optional[str]:
    """Render value into a D/DD/DDDD slot, or None if it doesn't fit."""
    if slot == "D":
        return str(value) if value < 10 else None
    if slot == "DD":
        return f"{value:02d}" if value < 100 else None
    return f"{value:04d}"


def year_fits_pivot(year: int) -> bool:
    return 1969 <= year <= 2068


# ---------------------------------------------------------------------------
# Field orders the parser can recover from each pattern, and when each is unambiguous
# ---------------------------------------------------------------------------

# Y = year, M = numeric month, D = day, N = month name.
NUMERIC_ORDERS = [("Y", "M", "D"), ("Y", "D", "M"), ("M", "D", "Y"), ("D", "M", "Y")]


def numeric_order_is_detectable(order: Tuple[str, str, str], slots: List[str], d: date) -> bool:
    year_slot = slots[order.index("Y")]
    if year_slot == "D":
        return False
    if any(len(slot) == 4 and field != "Y" for field, slot in zip(order, slots)):
        return False  # a day or month padded to four digits ("99/12/0025") isn't a real form
    if len(year_slot) == 2 and not year_fits_pivot(d.year):
        return False
    if order[0] == "Y" and len(year_slot) == 2 and d.year % 100 <= 31:
        return False  # a leading 2-digit value <= 31 is read as month/day, not year
    if order[0] != "Y" and len(slots[0]) == 4:
        return False
    if order in (("Y", "D", "M"), ("D", "M", "Y")):
        return d.day > 12  # day-before-month is only detectable when the day can't be a month
    return True


def alpha_order(pattern_fields: List[str]) -> List[Tuple[str, ...]]:
    """Possible orders for an alphanumeric pattern; the M slot is the month name."""
    numeric = [i for i, f in enumerate(pattern_fields) if f != "M"]
    orders = []
    for year_pos in numeric:
        order = ["N" if f == "M" else "D" for f in pattern_fields]
        order[year_pos] = "Y"
        orders.append(tuple(order))
    return orders


def alpha_order_is_detectable(order: Tuple[str, ...], slots: List[str], d: date) -> bool:
    year_slot = slots[order.index("Y")]
    if year_slot == "D":
        return False
    if len(year_slot) == 2 and not year_fits_pivot(d.year):
        return False
    numeric_positions = [i for i, f in enumerate(order) if f != "N"]
    first_numeric = numeric_positions[0]
    if order[first_numeric] == "Y":
        # A leading year is recognised by a 4-digit slot or a 2-digit value > 31.
        if order[0] == "N":
            return False  # "Dec 2025 12" is not a pattern; month-first always has the year last
        return len(year_slot) == 4 or d.year % 100 > 31
    # Year last: rejected only if the leading day slot holds a 4-digit number.
    return len(slots[first_numeric]) != 4


FIELD_FORMAT = {"M": "MM", "D": "dd"}


def field_format(field: str, slot: str, month_name: str = "") -> str:
    if field == "Y":
        return "yyyy" if len(slot) == 4 else "yy"
    if field == "N":
        return month_format(month_name)
    return FIELD_FORMAT[field]


def render_date(
    order: Sequence[str], slots: List[str], delims: Sequence[str], d: date, month_name: str = ""
) -> Optional[Tuple[str, str]]:
    """Return (text, identified_format) or None if d doesn't fit the slots."""
    text_parts, fmt_parts = [], []
    for field, slot in zip(order, slots):
        if field == "N":
            rendered: Optional[str] = month_name
        elif field == "Y":
            rendered = render_number(d.year if len(slot) == 4 else d.year % 100, slot)
        elif field == "M":
            rendered = render_number(d.month, slot)
        else:
            rendered = render_number(d.day, slot)
        if rendered is None:
            return None
        text_parts.append(rendered)
        fmt_parts.append(field_format(field, slot, month_name))
    text = text_parts[0] + delims[0] + text_parts[1] + delims[1] + text_parts[2]
    fmt = fmt_parts[0] + delims[0] + fmt_parts[1] + delims[1] + fmt_parts[2]
    return text, fmt


# ---------------------------------------------------------------------------
# Case generators
# ---------------------------------------------------------------------------

UNIQUE_PATTERNS = list(dict.fromkeys(Dictionary.PATTERN))
NUMERIC_PATTERNS = [p for p in UNIQUE_PATTERNS if "M" not in p]
ALPHA_PATTERNS = [p for p in UNIQUE_PATTERNS if "M" in p]


def numeric_delimiter_pairs() -> List[Tuple[str, str]]:
    return [(s, s) for s in NUMERIC_DELIMITERS]


def numeric_render_is_plausible(order: Sequence[str], slots: List[str], delim: str) -> bool:
    """Mirror of the parser's plausibility rules for all-numeric dates."""
    two_digit_year = len(slots[order.index("Y")]) == 2
    if delim == " " and two_digit_year:
        return False  # "8 9 10" is a list of numbers
    if delim == "." and two_digit_year and "D" in slots:
        return False  # "3.10.12" is a version number
    return True


def alpha_render_is_plausible(order: Sequence[str], slots: List[str], delims: Sequence[str]) -> bool:
    """Mirror of the parser's plausibility rules for month-name dates."""
    two_digit_year = len(slots[order.index("Y")]) == 2
    if delims[0] == "," and delims[1] != ",":
        return False  # "12,Dec 2025"; all-comma "2025,01,Jan" is fine
    if order[0] == "N" and two_digit_year and "," not in delims[1]:
        return False  # "May 12 13 people"; "May 12, 13" is fine
    return True


def alpha_delimiters_for(delim_slots: List[str]) -> List[Tuple[str, str]]:
    options = [ALPHA_DELIMITERS if len(s) == 1 else ALPHA_DOUBLE_DELIMITERS for s in delim_slots]
    pairs = []
    if len(delim_slots[1]) == 1:
        options[1] = options[1] + [","]
    for first, second in product(*options):
        # Two single delimiters must match, except a comma before the year ("Dec 12,2025").
        if len(first) == len(second) == 1 and first != second and second != ",":
            continue
        pairs.append((first, second))
    return pairs


def numeric_cases(pattern: str, dates: Sequence[date] = ()) -> List[Case]:
    slots, delim_slots = split_pattern(pattern)
    cases: Dict[str, Case] = {}
    for d in dates or sample_dates():
        for order in NUMERIC_ORDERS:
            if not numeric_order_is_detectable(order, slots, d):
                continue
            for delims in numeric_delimiter_pairs():
                if not numeric_render_is_plausible(order, slots, delims[0]):
                    continue
                rendered = render_date(order, slots, delims, d)
                if rendered is None:
                    continue
                text, fmt = rendered
                cases.setdefault(text, Case(text, d.isoformat(), fmt))
    return list(cases.values())


def alpha_cases(pattern: str, dates: Sequence[date] = (), spellings: bool = True) -> List[Case]:
    slots, delim_slots = split_pattern(pattern)
    cases: Dict[str, Case] = {}
    for d in dates or sample_dates(years=(2025, 1999, 2005)):
        short, full = MONTHS_SHORT[d.month - 1], MONTHS_FULL[d.month - 1]
        names = [short, full, short.lower(), full.upper()] if spellings else [short]
        for order in alpha_order(slots):
            if not alpha_order_is_detectable(order, slots, d):
                continue
            for delims, name in product(alpha_delimiters_for(delim_slots), names):
                if not alpha_render_is_plausible(order, slots, delims):
                    continue
                rendered = render_date(order, slots, delims, d, name)
                if rendered is None:
                    continue
                text, fmt = rendered
                cases.setdefault(text, Case(text, d.isoformat(), fmt))
    return list(cases.values())


def representative_date_cases(per_pattern: Optional[int] = None) -> List[Case]:
    """A few renderings of each pattern, used as the base for time/context combinations."""
    reps: List[Case] = []
    numeric_dates = [date(2024, 7, 4), date(1999, 12, 25)]
    for pattern in NUMERIC_PATTERNS:
        found = [c for c in numeric_cases(pattern, numeric_dates) if c.text[2] in "-/" or c.text[4] in "-/"]
        reps.extend(found[:per_pattern])
    alpha_dates = [date(2025, 7, 4), date(1999, 12, 25)]
    for pattern in ALPHA_PATTERNS:
        found = [c for c in alpha_cases(pattern, alpha_dates, spellings=False) if "." not in c.text]
        reps.extend(found[:per_pattern])
    return reps


def render_time(pattern: str, t: time, meridiem: Optional[str]) -> Optional[Tuple[str, str, str]]:
    """Return (text, value, identified_format) for a TIME_PATTERN, or None if t doesn't fit."""
    pattern = pattern.rstrip()
    hour = t.hour
    if meridiem:
        if hour == 0 or hour > 12:
            return None
    h = render_number(hour, "D" if pattern.startswith("D:") else "DD")
    if h is None:
        return None
    text = f"{h}:{t.minute:02d}:{t.second:02d}"
    fmt = "HH:mm:ss"
    value_hour = hour
    if meridiem:
        value_hour = hour % 12 + (12 if meridiem.lower() == "pm" else 0)
        fmt = "hh:mm:ss"
    value = f"{value_hour:02d}:{t.minute:02d}:{t.second:02d}"
    millis_sep = pattern[-4] if pattern[-4] in ".," else None
    if millis_sep:
        millis = t.microsecond // 1000
        text += f"{millis_sep}{millis:03d}"
        fmt += f"{millis_sep}SSS"
        value += f".{millis:03d}"
    if meridiem:
        text += f" {meridiem}"
        fmt += " a"
    return text, value, fmt


SAMPLE_TIMES = [
    time(0, 0, 0), time(1, 2, 3, 4000), time(9, 59, 59, 999000), time(12, 0, 0),
    time(12, 30, 45, 500000), time(13, 5, 7, 123000), time(23, 59, 59, 1000),
]


ALL_MERIDIEMS = [None, "AM", "PM", "am", "pm"]


def date_time_cases(
    date_cases: Sequence[Case],
    separators: Sequence[str] = DATE_TIME_SEPARATORS,
    times: Sequence[time] = SAMPLE_TIMES,
    meridiems: Sequence[Optional[str]] = ALL_MERIDIEMS,
) -> List[Case]:
    cases: Dict[str, Case] = {}
    time_patterns = list(dict.fromkeys(p.rstrip() for p in Dictionary.TIME_PATTERN))
    for base, sep, pattern, t, meridiem in product(date_cases, separators, time_patterns, times, meridiems):
        rendered = render_time(pattern, t, meridiem)
        if rendered is None:
            continue
        # Mixing a "-" date/time separator with a "-" or " " date delimiter is ambiguous to read.
        if sep == "-" and ("-" in base.text or " " in base.text):
            continue
        # ISO "T" only follows a numeric date part ("2025-12-12T..."), never a month name.
        if sep == "T" and base.text[-1].isalpha():
            continue
        t_text, t_value, t_fmt = rendered
        text = f"{base.text}{sep}{t_text}"
        sep_fmt = "'T'" if sep == "T" else sep
        cases.setdefault(text, Case(text, f"{base.value} {t_value}", f"{base.fmt}{sep_fmt}{t_fmt}"))
    return list(cases.values())


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class MatrixTestCase(unittest.TestCase):
    MAX_REPORTED = 25

    def check_cases(
        self, cases: Sequence[Case], prefix: str = "", suffix: str = "", check_span: bool = False
    ) -> None:
        self.assertTrue(cases, "generator produced no cases")
        failures = []
        for case in cases:
            text = f"{prefix}{case.text}{suffix}"
            results = Parser().parse(text)
            got = [(r.date_time_string, r.identified_date_format) for r in results]
            problem = None
            if got != [(case.value, case.fmt)]:
                problem = f"got {got}, expected {[(case.value, case.fmt)]}"
            elif check_span:
                r = results[0]
                span = text[r.start : r.end + 1]
                if (r.start, span) != (len(prefix), case.text):
                    problem = f"span {span!r} at {r.start}, expected {case.text!r} at {len(prefix)}"
            if problem:
                failures.append(f"{text!r}: {problem}")
        if failures:
            shown = "\n  ".join(failures[: self.MAX_REPORTED])
            self.fail(f"{len(failures)} of {len(cases)} cases failed:\n  {shown}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPatternCoverage(unittest.TestCase):
    def test_every_pattern_generates_cases(self) -> None:
        # Fails if a new PATTERN entry is added that this module can't render.
        for pattern in NUMERIC_PATTERNS:
            with self.subTest(pattern=pattern):
                self.assertTrue(numeric_cases(pattern), pattern)
        for pattern in ALPHA_PATTERNS:
            with self.subTest(pattern=pattern):
                self.assertTrue(alpha_cases(pattern), pattern)


class TestNumericPatterns(MatrixTestCase):
    """Each numeric PATTERN x field order x delimiter (single and mixed) x sample dates."""


class TestAlphaPatterns(MatrixTestCase):
    """Each month-name PATTERN x field order x delimiter x 4 month spellings x sample dates."""


def _add_pattern_tests() -> None:
    def make(generator, pattern):
        return lambda self: self.check_cases(generator(pattern))

    for pattern in NUMERIC_PATTERNS:
        name = "test_" + pattern.replace("*", "_")
        setattr(TestNumericPatterns, name, make(numeric_cases, pattern))
    for pattern in ALPHA_PATTERNS:
        name = "test_" + pattern.replace("*", "_")
        setattr(TestAlphaPatterns, name, make(alpha_cases, pattern))


_add_pattern_tests()


class TestDateTimeMatrix(MatrixTestCase):
    """Every date pattern x every TIME_PATTERN x separator x sample time x meridiem."""

    def test_numeric_dates_with_times(self) -> None:
        bases = [c for c in representative_date_cases() if not any(ch.isalpha() for ch in c.text)]
        self.check_cases(date_time_cases(bases))

    def test_alpha_dates_with_times(self) -> None:
        bases = [c for c in representative_date_cases() if any(ch.isalpha() for ch in c.text)]
        self.check_cases(date_time_cases(bases, separators=[" ", "T"]))


class TestContexts(MatrixTestCase):
    """Representative dates and date-times embedded in running text, including span checks."""

    PREFIXES = ["", "On ", "(", "date=", "x\n", "\t"]
    DATE_SUFFIXES = ["", " ok", ".", ")", ";", "\n", ", then", "x"]
    TIME_SUFFIXES = ["", " ok", ".", ")", ";", "\n", ", then"]

    def test_dates_in_context(self) -> None:
        bases = representative_date_cases()
        for prefix, suffix in product(self.PREFIXES, self.DATE_SUFFIXES):
            # A letter glued to a trailing month name makes a different word ("Decx").
            cases = [c for c in bases if not (suffix[:1].isalpha() and c.text[-1].isalpha())]
            with self.subTest(prefix=prefix, suffix=suffix):
                self.check_cases(cases, prefix, suffix, check_span=True)

    def test_date_times_in_context(self) -> None:
        bases = representative_date_cases(per_pattern=1)
        cases = date_time_cases(
            bases, separators=[" ", "T"], times=[time(9, 5, 7, 123000), time(23, 59, 59)], meridiems=[None, "PM"]
        )
        for prefix, suffix in product(self.PREFIXES, self.TIME_SUFFIXES):
            with self.subTest(prefix=prefix, suffix=suffix):
                self.check_cases(cases, prefix, suffix, check_span=True)

    def test_weekday_prefix_on_every_alpha_pattern(self) -> None:
        cases = []
        for c in representative_date_cases():
            if not any(ch.isalpha() for ch in c.text):
                continue
            wd = WEEKDAYS_FULL[date.fromisoformat(c.value).weekday()]
            for prefix in (f"{wd}, ", f"{wd[:3]}, ", f"{wd} "):
                cases.append(Case(prefix + c.text, c.value, c.fmt))
        self.check_cases(cases)


class TestManyDatesInOneText(MatrixTestCase):
    def test_all_representatives_in_one_document(self) -> None:
        bases = representative_date_cases()
        # Labels carry no digits: a number just before a date is a known bug (see TestKnownBugs).
        text = "\n".join(f"Entry: {c.text} done." for c in bases)
        results = Parser().parse(text)
        self.assertEqual(
            [(r.date_time_string, r.identified_date_format) for r in results],
            [(c.value, c.fmt) for c in bases],
        )
        for r, c in zip(results, bases):
            self.assertEqual(text[r.start : r.end + 1], c.text)


class TestUnsupportedForms(MatrixTestCase):
    """Inputs outside the supported patterns: the date must still be found and nothing invented."""

    def test_partial_or_malformed_times_keep_the_date(self) -> None:
        self.check_cases(
            [
                Case("2025-12-12 10:20", "2025-12-12", "yyyy-MM-dd"),
                Case("2025-12-12 10:20:30.5", "2025-12-12", "yyyy-MM-dd"),
                Case("2025-12-12 10:20:30,5", "2025-12-12", "yyyy-MM-dd"),
                Case("2025-12-12 24:00:00", "2025-12-12", "yyyy-MM-dd"),
                Case("2025-12-12 13:00:00 PM", "2025-12-12", "yyyy-MM-dd"),
            ]
        )

    def test_unsupported_delimiters(self) -> None:
        for text in ("2025|12|12", "2025_12_12", "2025 Dec. 12", "12|Dec|2025"):
            with self.subTest(text=text):
                self.assertEqual(Parser().parse(text), [])

    def test_long_milliseconds_truncated_to_three_digits(self) -> None:
        self.check_cases([Case("2025-12-12 10:20:30.12345", "2025-12-12 10:20:30.123", "yyyy-MM-dd HH:mm:ss.SSS")])


def raw_renders(pattern: str, delim_pairs: Sequence[Tuple[str, str]], dates: Sequence[date]) -> List[str]:
    """Render a pattern with the given separators, skipping the parser's plausibility rules."""
    slots, _ = split_pattern(pattern)
    texts: Dict[str, None] = {}
    for d in dates:
        if "M" in pattern:
            orders = [o for o in alpha_order(slots) if alpha_order_is_detectable(o, slots, d)]
        else:
            orders = [o for o in NUMERIC_ORDERS if numeric_order_is_detectable(o, slots, d)]
        for order, delims in product(orders, delim_pairs):
            rendered = render_date(order, slots, delims, d, MONTHS_SHORT[d.month - 1])
            if rendered:
                texts[rendered[0]] = None
    return list(texts)


REJECTION_DATES = [date(2024, 7, 14), date(1999, 12, 25), date(2005, 3, 4)]


class TestImplausibleMatches(MatrixTestCase):
    """Text that fits a pattern but is almost never a date must not be reported as one."""

    def check_rejected(self, texts: Sequence[str]) -> None:
        self.assertTrue(texts, "generator produced no cases")
        failures = []
        for text in texts:
            results = Parser().parse(text)
            if results:
                failures.append(f"{text!r}: got {[(r.original_text, r.date_time_string) for r in results]}")
        if failures:
            shown = "\n  ".join(failures[: self.MAX_REPORTED])
            self.fail(f"{len(failures)} of {len(texts)} inputs were accepted:\n  {shown}")

    def test_numeric_with_comma_or_colon_separators(self) -> None:
        # "3,4,25" is a list of numbers and "10:30:45" is a time.
        pairs = [(",", ","), (":", ":")]
        self.check_rejected([t for p in NUMERIC_PATTERNS for t in raw_renders(p, pairs, REJECTION_DATES)])

    def test_numeric_with_mixed_separators(self) -> None:
        pairs = [("/", "-"), ("-", "/"), (".", "-"), ("-", "."), ("/", "."), (" ", "/"), ("/", " "), ("\\", "/")]
        self.check_rejected([t for p in NUMERIC_PATTERNS for t in raw_renders(p, pairs, REJECTION_DATES)])

    def test_space_separated_two_digit_year(self) -> None:
        texts = [
            t
            for p in NUMERIC_PATTERNS
            if "DDDD" not in p
            for t in raw_renders(p, [(" ", " ")], REJECTION_DATES)
            if len(re.findall(r"[0-9]+", t)[0]) != 4 and len(re.findall(r"[0-9]+", t)[-1]) != 4
        ]
        self.check_rejected(texts + ["qty 7 8 9 10 11 12 13", "scores 3 4 5 6", "rows 11 12 13"])

    def test_dotted_two_digit_year_with_single_digit_field(self) -> None:
        texts = [
            t
            for p in NUMERIC_PATTERNS
            if "DDDD" not in p and "*D*" in f"*{p}*".replace("DD", "XX")
            for t in raw_renders(p, [(".", ".")], REJECTION_DATES)
        ]
        self.check_rejected(texts + ["version 3.10.12", "Python 3.12.1", "v1.2.25"])

    def test_part_of_a_longer_number_chain(self) -> None:
        texts = []
        for p in ("DDDD*DD*DD", "DD*DD*DDDD", "D*D*DD", "DD*DD*DD"):
            for t in raw_renders(p, [("/", "/"), ("-", "-"), (".", ".")], REJECTION_DATES):
                sep = next(ch for ch in t if not ch.isdigit())
                if sep == "." and re.search(r"(?<![0-9])[0-9](?![0-9])", t) and len(t.split(".")[-1]) == 2:
                    continue  # already rejected as a version number
                texts += [f"1{sep}{t}", f"{t}{sep}1", f"12{sep}{t}{sep}34"]
        self.check_rejected(texts + ["1.2.3.2024", "192.168.1.12", "10.0.0.12", "/a/12/12/2025/1"])

    def test_four_digit_year_out_of_range(self) -> None:
        self.check_rejected(["3000-01-01", "9999-12-31", "12/12/3000", "Dec 12, 4000", "12 Dec 5000", "4000 Dec 12"])

    def test_month_name_with_comma_first_or_mixed_separators(self) -> None:
        # A leading comma is only accepted when both separators are commas ("2025,01,Jan").
        texts = []
        for p in ALPHA_PATTERNS:
            if "**" in p:
                continue
            texts += raw_renders(p, [(",", " "), (",", "-"), (" ", "-"), ("-", "/"), ("/", ".")], REJECTION_DATES)
        texts += ["12,Dec, 2025", "12,December. 2025"]
        self.check_rejected(texts)

    def test_month_first_two_digit_year_without_comma(self) -> None:
        texts = raw_renders("M*DD*DD", [(" ", " "), ("-", "-"), ("/", "/")], REJECTION_DATES)
        texts += raw_renders("M*D*DD", [(" ", " "), ("-", "-")], REJECTION_DATES)
        self.check_rejected(texts + ["May 12 13 people", "Mar 3 45 times", "Jun 10 20 items"])

    def test_times_are_not_dates(self) -> None:
        self.check_rejected(["meeting at 10:30:45", "elapsed 01:02:03", "12:12:25", "at 23:59:59 sharp"])

    def test_sentences_full_of_numbers(self) -> None:
        self.check_rejected(
            [
                "Order 1234 has 5 6 7 items and costs 12.50",
                "Call 555-12-34 or 555 12 34",
                "Totals: 3,4,25 / 12,12,2025",
                "Ratio 1/2/3 and 4/5/6",
                "Build 2.31.10 shipped",
                "See section 4.12.25 for details",
            ]
        )


class TestScannerRecovery(MatrixTestCase):
    """The scanner must recover when a candidate dies and keep looking for later dates."""

    def test_number_just_before_a_date(self) -> None:
        self.check_cases(
            [
                Case("Entry 1: 2024/07/04", "2024-07-04", "yyyy/MM/dd"),
                Case("1 2024/07/04", "2024-07-04", "yyyy/MM/dd"),
                Case("Item 12 2024-07-04", "2024-07-04", "yyyy-MM-dd"),
                Case("page 3, 2024-07-04", "2024-07-04", "yyyy-MM-dd"),
                Case("1. 2024-07-04", "2024-07-04", "yyyy-MM-dd"),
                Case("1 12/12/2025", "2025-12-12", "MM/dd/yyyy"),
                Case("1 12-12-2025", "2025-12-12", "MM-dd-yyyy"),
                Case("Room 5 12.12.2025", "2025-12-12", "MM.dd.yyyy"),
                Case("1 5 Dec 2025", "2025-12-05", "dd MMM yyyy"),
                Case("No. 7 December 12, 2025", "2025-12-12", "MMMMM dd, yyyy"),
            ],
            check_span=False,
        )

    def test_number_before_year_month_day_does_not_crash(self) -> None:
        self.check_cases([Case("2: 2025 Jul 04", "2025-07-04", "yyyy MMM dd")])

    def test_numbered_list_with_every_representative(self) -> None:
        bases = representative_date_cases()
        text = "\n".join(f"{i}. Entry {i}: {c.text} (ref {i * 7})" for i, c in enumerate(bases, start=1))
        results = Parser().parse(text)
        self.assertEqual(
            [(r.date_time_string, r.identified_date_format) for r in results],
            [(c.value, c.fmt) for c in bases],
        )
        for r, c in zip(results, bases):
            self.assertEqual(text[r.start : r.end + 1], c.text)

    def test_back_to_back_dates(self) -> None:
        text = "2025-12-12 2025-12-13 12/14/2025 Dec 15, 2025 2025-12-16 10:20:30 2025-12-17"
        self.assertEqual(
            [r.date_time_string for r in Parser().parse(text)],
            ["2025-12-12", "2025-12-13", "2025-12-14", "2025-12-15", "2025-12-16 10:20:30", "2025-12-17"],
        )

    def test_number_after_a_complete_date_is_left_alone(self) -> None:
        self.check_cases(
            [
                Case("On 12/12/25 10 people came", "2025-12-12", "MM/dd/yy"),
                Case("On 5 Dec 25 people came", "2025-12-05", "dd MMM yy"),
                Case("12 Dec 25, 30 people", "2025-12-12", "dd MMM yy"),
                Case("2025-12-12 10 items", "2025-12-12", "yyyy-MM-dd"),
            ]
        )
        values = [r.date_time_string for r in Parser().parse("12/12/2025 10 Dec 2025")]
        self.assertEqual(values, ["2025-12-12", "2025-12-10"])


class TestMeridiem(MatrixTestCase):
    def test_word_starting_with_am_or_pm_is_not_a_meridiem(self) -> None:
        self.check_cases(
            [
                Case("2025-12-12 10:20:30 amazing", "2025-12-12 10:20:30", "yyyy-MM-dd HH:mm:ss"),
                Case("2025-12-12 10:20:30 pmt", "2025-12-12 10:20:30", "yyyy-MM-dd HH:mm:ss"),
                Case("2025-12-12 10:20:30 Amsterdam", "2025-12-12 10:20:30", "yyyy-MM-dd HH:mm:ss"),
            ]
        )

    def test_meridiem_without_space(self) -> None:
        cases = []
        for meridiem, hour in (("AM", "10"), ("PM", "22"), ("am", "10"), ("pm", "22")):
            cases.append(Case(f"2025-12-12 10:20:30{meridiem}", f"2025-12-12 {hour}:20:30", "yyyy-MM-dd hh:mm:ssa"))
            cases.append(
                Case(f"2025-12-12 10:20:30.250{meridiem}", f"2025-12-12 {hour}:20:30.250", "yyyy-MM-dd hh:mm:ss.SSSa")
            )
        for prefix, suffix in product(["", "at "], ["", ".", " next", ")"]):
            with self.subTest(prefix=prefix, suffix=suffix):
                self.check_cases(cases, prefix, suffix, check_span=True)

    def test_meridiem_followed_by_punctuation(self) -> None:
        self.check_cases(
            [
                Case("2025-12-12 10:20:30 PM.", "2025-12-12 22:20:30", "yyyy-MM-dd hh:mm:ss a"),
                Case("2025-12-12 10:20:30 pm,", "2025-12-12 22:20:30", "yyyy-MM-dd hh:mm:ss a"),
                Case("2025-12-12 10:20:30 AM)", "2025-12-12 10:20:30", "yyyy-MM-dd hh:mm:ss a"),
            ],
            check_span=False,
        )


if __name__ == "__main__":
    unittest.main()
