"""Exhaustive tests for dateparserpython.Parser.

Run with:  python3 -m unittest discover -s tests -v
(pytest also picks these up if installed.)

Expected values come from the standard library's datetime, not from the parser,
so these tests catch regressions rather than snapshotting current behaviour.
"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import date, datetime, timedelta
from typing import Iterator, List, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dateparserpython import LocalDateModel, Parser  # noqa: E402

MONTHS_FULL = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
MONTHS_SHORT = [m[:3] for m in MONTHS_FULL]
WEEKDAYS_FULL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WEEKDAYS_SHORT = [w[:3] for w in WEEKDAYS_FULL]

NUMERIC_DELIMITERS = ["/", "-", ".", " ", "\\"]


def parse(text: str) -> List[LocalDateModel]:
    return Parser().parse(text)


def days_of(year: int) -> Iterator[date]:
    day = date(year, 1, 1)
    while day.year == year:
        yield day
        day += timedelta(days=1)


def full_month_format(month_name: str) -> str:
    # The parser reports MMMMM whenever the text contains a full month name;
    # "May" is both the short and the full name.
    return "MMMMM" if month_name.lower() in {m.lower() for m in MONTHS_FULL} else "MMM"


class ParserTestCase(unittest.TestCase):
    def assertSingleDate(
        self,
        text: str,
        expected_value: str,
        expected_format: Optional[str] = None,
        expected_original: Optional[str] = None,
    ) -> LocalDateModel:
        results = parse(text)
        self.assertEqual(
            len(results), 1, f"{text!r}: expected 1 date, got {[str(r) for r in results]}"
        )
        result = results[0]
        self.assertEqual(result.date_time_string, expected_value, f"value for {text!r}")
        if expected_format is not None:
            self.assertEqual(result.identified_date_format, expected_format, f"format for {text!r}")
        if expected_original is not None:
            self.assertEqual(result.original_text, expected_original, f"original_text for {text!r}")
        return result

    def assertNoDate(self, text: str) -> None:
        results = parse(text)
        self.assertEqual(results, [], f"{text!r}: expected no date, got {[str(r) for r in results]}")

    def runCases(self, cases: List[Tuple[str, str, Optional[str]]]) -> None:
        for text, expected_value, expected_format in cases:
            with self.subTest(text=text):
                self.assertSingleDate(text, expected_value, expected_format)


# ---------------------------------------------------------------------------
# Numeric dates: every day of a leap and a non-leap year, every delimiter
# ---------------------------------------------------------------------------


class TestNumericEveryDay(ParserTestCase):
    YEARS = [2024, 2025]

    def _check(self, render, expected_format_for) -> None:
        for year in self.YEARS:
            for day in days_of(year):
                for delim in NUMERIC_DELIMITERS:
                    text = render(day, delim)
                    fmt = expected_format_for(day, delim)
                    if fmt is None:
                        continue
                    with self.subTest(text=text):
                        self.assertSingleDate(text, day.isoformat(), fmt)

    def test_yyyy_mm_dd_zero_padded(self) -> None:
        self._check(
            lambda d, s: f"{d.year}{s}{d.month:02d}{s}{d.day:02d}",
            lambda d, s: f"yyyy{s}MM{s}dd",
        )

    def test_yyyy_m_d_unpadded(self) -> None:
        self._check(
            lambda d, s: f"{d.year}{s}{d.month}{s}{d.day}",
            lambda d, s: f"yyyy{s}MM{s}dd",
        )

    def test_mm_dd_yyyy(self) -> None:
        # Month-first is the default when both day and month are <= 12.
        self._check(
            lambda d, s: f"{d.month:02d}{s}{d.day:02d}{s}{d.year}",
            lambda d, s: f"MM{s}dd{s}yyyy",
        )

    def test_m_d_yyyy_unpadded(self) -> None:
        self._check(
            lambda d, s: f"{d.month}{s}{d.day}{s}{d.year}",
            lambda d, s: f"MM{s}dd{s}yyyy",
        )

    def test_dd_mm_yyyy_when_unambiguous(self) -> None:
        # Day-first can only be detected when the day is > 12.
        self._check(
            lambda d, s: f"{d.day:02d}{s}{d.month:02d}{s}{d.year}",
            lambda d, s: f"dd{s}MM{s}yyyy" if d.day > 12 else None,
        )

    # Space-separated numbers with a two-digit year are rejected (see test_format_matrix.TestImplausibleMatches).

    def test_mm_dd_yy(self) -> None:
        self._check(
            lambda d, s: f"{d.month:02d}{s}{d.day:02d}{s}{d.year % 100:02d}",
            lambda d, s: f"MM{s}dd{s}yy" if s != " " else None,
        )

    def test_dd_mm_yy_when_unambiguous(self) -> None:
        self._check(
            lambda d, s: f"{d.day:02d}{s}{d.month:02d}{s}{d.year % 100:02d}",
            lambda d, s: f"dd{s}MM{s}yy" if d.day > 12 and s != " " else None,
        )


class TestNumericYyFirst(ParserTestCase):
    def test_yy_mm_dd_when_year_over_31(self) -> None:
        # A leading two-digit value can only be read as a year if it can't be a day.
        cases = []
        for year in (1999, 1969, 2032, 2045, 2068):
            for day in (date(year, 1, 1), date(year, 6, 15), date(year, 12, 31)):
                text = f"{year % 100:02d}/{day.month:02d}/{day.day:02d}"
                cases.append((text, day.isoformat(), "yy/MM/dd"))
        self.runCases(cases)


class TestTwoDigitYearPivot(ParserTestCase):
    def test_pivot_matches_strptime(self) -> None:
        for yy in range(100):
            text = f"06/15/{yy:02d}"
            expected = datetime.strptime(text, "%m/%d/%y").date().isoformat()
            with self.subTest(text=text):
                self.assertSingleDate(text, expected, "MM/dd/yy")


class TestLeapYears(ParserTestCase):
    def test_feb_29_on_leap_years(self) -> None:
        for year in (1996, 2000, 2004, 2020, 2024, 2028):
            for text in (f"{year}-02-29", f"02/29/{year}", f"29.02.{year}"):
                with self.subTest(text=text):
                    self.assertSingleDate(text, f"{year}-02-29")

    def test_feb_29_rejected_on_non_leap_years(self) -> None:
        for year in (2019, 2021, 2023, 2025):
            for text in (f"{year}-02-29", f"02/29/{year}"):
                with self.subTest(text=text):
                    self.assertNoDate(text)

    def test_feb_29_rejected_on_century_non_leap_years(self) -> None:
        for text in ("1800-02-29", "1900-02-29", "2100-02-29", "02/29/2100"):
            with self.subTest(text=text):
                self.assertNoDate(text)

    def test_feb_29_on_two_digit_years_uses_pivoted_century(self) -> None:
        self.assertSingleDate("02/29/00", "2000-02-29", "MM/dd/yy")
        self.assertSingleDate("02/29/72", "1972-02-29", "MM/dd/yy")
        self.assertNoDate("02/29/01")


class TestInvalidNumericDates(ParserTestCase):
    def test_impossible_dates_rejected(self) -> None:
        for text in (
            "2025-02-30",
            "2025-02-31",
            "2025-04-31",
            "2025-06-31",
            "2025-09-31",
            "2025-11-31",
            "2025-13-13",
            "2025-00-10",
            "04/31/2025",
            "13/13/2025",
            "32/01/2025",
            "2025-12-32",
        ):
            with self.subTest(text=text):
                self.assertNoDate(text)


# ---------------------------------------------------------------------------
# Alphanumeric dates: every month, short and full names, common layouts
# ---------------------------------------------------------------------------


class TestAlphanumericEveryMonth(ParserTestCase):
    DAYS = [1, 9, 15, 28]
    YEAR = 2025

    def _check(self, render, fmt_template, months) -> None:
        for month_index, month_name in enumerate(months, start=1):
            mmm = full_month_format(month_name)
            for day_num in self.DAYS:
                expected = date(self.YEAR, month_index, day_num).isoformat()
                for name in (month_name, month_name.lower(), month_name.upper()):
                    text = render(day_num, name, self.YEAR)
                    with self.subTest(text=text):
                        self.assertSingleDate(text, expected, fmt_template.replace("M*", mmm))

    def test_dd_mmm_yyyy(self) -> None:
        self._check(lambda d, m, y: f"{d:02d} {m} {y}", "dd M* yyyy", MONTHS_SHORT)

    def test_dd_mmmmm_yyyy(self) -> None:
        self._check(lambda d, m, y: f"{d:02d} {m} {y}", "dd M* yyyy", MONTHS_FULL)

    def test_dd_mmm_yyyy_hyphens(self) -> None:
        self._check(lambda d, m, y: f"{d:02d}-{m}-{y}", "dd-M*-yyyy", MONTHS_SHORT)

    def test_dd_mmmmm_comma_yyyy(self) -> None:
        self._check(lambda d, m, y: f"{d:02d} {m}, {y}", "dd M*, yyyy", MONTHS_FULL)

    def test_mmm_dd_comma_yyyy(self) -> None:
        self._check(lambda d, m, y: f"{m} {d:02d}, {y}", "M* dd, yyyy", MONTHS_SHORT)

    def test_mmmmm_dd_comma_yyyy(self) -> None:
        self._check(lambda d, m, y: f"{m} {d:02d}, {y}", "M* dd, yyyy", MONTHS_FULL)

    def test_mmm_dd_yyyy(self) -> None:
        self._check(lambda d, m, y: f"{m} {d:02d} {y}", "M* dd yyyy", MONTHS_SHORT)

    def test_yyyy_mmm_dd(self) -> None:
        self._check(lambda d, m, y: f"{y} {m} {d:02d}", "yyyy M* dd", MONTHS_SHORT)

    def test_unpadded_day(self) -> None:
        self._check(lambda d, m, y: f"{d} {m} {y}", "dd M* yyyy", MONTHS_SHORT)

    def test_yyyy_dd_mmm(self) -> None:
        self._check(lambda d, m, y: f"{y} {d:02d} {m}", "yyyy dd M*", MONTHS_SHORT)

    def test_yyyy_dd_mmmmm(self) -> None:
        self._check(lambda d, m, y: f"{y}-{d}-{m}", "yyyy-dd-M*", MONTHS_FULL)

    def test_all_comma_separators(self) -> None:
        self._check(lambda d, m, y: f"{y},{d:02d},{m}", "yyyy,dd,M*", MONTHS_SHORT)
        self._check(lambda d, m, y: f"{y},{m},{d:02d}", "yyyy,M*,dd", MONTHS_FULL)
        self._check(lambda d, m, y: f"{d:02d},{m},{y}", "dd,M*,yyyy", MONTHS_SHORT)
        self._check(lambda d, m, y: f"{m},{d:02d},{y}", "M*,dd,yyyy", MONTHS_SHORT)
        self.runCases(
            [
                ("2025,01,Jan", "2025-01-01", "yyyy,dd,MMM"),
                ("on 2025,01,Jan at noon", "2025-01-01", "yyyy,dd,MMM"),
                ("2025,01,Jan 10:20:30", "2025-01-01 10:20:30", "yyyy,dd,MMM HH:mm:ss"),
                ("12,Dec,25", "2025-12-12", "dd,MMM,yy"),
            ]
        )

    def test_uppercase_month_with_t(self) -> None:
        # "T" is only the ISO date/time separator between digits, not inside OCT/AUGUST.
        self.runCases(
            [
                ("15 OCT 2025", "2025-10-15", "dd MMM yyyy"),
                ("15 AUGUST 2025", "2025-08-15", "dd MMMMM yyyy"),
                ("SEPTEMBER 15, 2025", "2025-09-15", "MMMMM dd, yyyy"),
                ("2025-12-12T10:20:30", "2025-12-12 10:20:30", "yyyy-MM-dd'T'HH:mm:ss"),
            ]
        )


class TestDateEndingOnMonth(ParserTestCase):
    def test_terminators(self) -> None:
        for text in ("2025 15 Dec", "2025 15 Dec.", "x 2025 15 Dec y", "(2025 15 Dec)", "2025 15 Dec\nnext"):
            with self.subTest(text=text):
                self.assertSingleDate(text, "2025-12-15", "yyyy dd MMM")

    def test_month_prefix_of_longer_word_is_not_a_date(self) -> None:
        for text in ("2025 15 decimal", "2025 15 mayor", "2025 15 marching"):
            with self.subTest(text=text):
                self.assertNoDate(text)


class TestAlphanumericTwoDigitYear(ParserTestCase):
    def test_two_digit_year_over_31(self) -> None:
        self.runCases(
            [
                ("12 Dec 99", "1999-12-12", "dd MMM yy"),
                ("Dec 12, 45", "2045-12-12", "MMM dd, yy"),
                ("99 Dec 12", "1999-12-12", "yy MMM dd"),
            ]
        )

    def test_two_digit_year_31_or_less(self) -> None:
        self.runCases(
            [
                ("12 Dec 25", "2025-12-12", "dd MMM yy"),
                ("Dec 12, 25", "2025-12-12", "MMM dd, yy"),
                ("01 January 05", "2005-01-01", "dd MMMMM yy"),
                ("25 Dec 12", "2012-12-25", "dd MMM yy"),
            ]
        )


class TestWeekdayPrefix(ParserTestCase):
    def test_every_weekday_short_and_full(self) -> None:
        for offset in range(7):
            day = date(2025, 12, 8) + timedelta(days=offset)  # Mon 8 Dec .. Sun 14 Dec
            short_wd, full_wd = WEEKDAYS_SHORT[day.weekday()], WEEKDAYS_FULL[day.weekday()]
            cases = [
                (f"{short_wd}, Dec {day.day}, 2025", "MMM dd, yyyy"),
                (f"{full_wd}, December {day.day}, 2025", "MMMMM dd, yyyy"),
                (f"{full_wd} {day.day} December 2025", "dd MMMMM yyyy"),
            ]
            for text, fmt in cases:
                with self.subTest(text=text):
                    self.assertSingleDate(text, day.isoformat(), fmt)


# ---------------------------------------------------------------------------
# Date + time
# ---------------------------------------------------------------------------


class TestDateTime24Hour(ParserTestCase):
    TIMES = ["00:00:00", "00:00:01", "01:02:03", "09:05:07", "11:59:59", "12:00:00",
             "12:30:45", "13:00:00", "18:45:30", "23:59:59"]

    def test_space_separator(self) -> None:
        for t in self.TIMES:
            with self.subTest(time=t):
                self.assertSingleDate(f"2025-12-12 {t}", f"2025-12-12 {t}", "yyyy-MM-dd HH:mm:ss")

    def test_t_separator(self) -> None:
        for t in self.TIMES:
            with self.subTest(time=t):
                self.assertSingleDate(f"2025-12-12T{t}", f"2025-12-12 {t}", "yyyy-MM-dd'T'HH:mm:ss")

    def test_milliseconds_dot(self) -> None:
        for t in self.TIMES:
            with self.subTest(time=t):
                self.assertSingleDate(
                    f"2025-12-12 {t}.123", f"2025-12-12 {t}.123", "yyyy-MM-dd HH:mm:ss.SSS"
                )

    def test_milliseconds_comma(self) -> None:
        for t in self.TIMES:
            with self.subTest(time=t):
                self.assertSingleDate(
                    f"2025-12-12 {t},456", f"2025-12-12 {t}.456", "yyyy-MM-dd HH:mm:ss,SSS"
                )

    def test_single_digit_hour(self) -> None:
        self.assertSingleDate("2025-12-12 9:05:07", "2025-12-12 09:05:07", "yyyy-MM-dd HH:mm:ss")

    def test_time_after_other_date_layouts(self) -> None:
        self.runCases(
            [
                ("12/12/2025 10:20:30", "2025-12-12 10:20:30", "MM/dd/yyyy HH:mm:ss"),
                ("25.12.2025 10:20:30", "2025-12-25 10:20:30", "dd.MM.yyyy HH:mm:ss"),
                ("2025/12/12 10:20:30", "2025-12-12 10:20:30", "yyyy/MM/dd HH:mm:ss"),
            ]
        )

    def test_invalid_time_keeps_date(self) -> None:
        for t in ("24:00:00", "23:60:00", "23:59:60"):
            with self.subTest(time=t):
                self.assertSingleDate(f"2025-12-12 {t}", "2025-12-12")


class TestDateTime12Hour(ParserTestCase):
    def test_every_hour_and_meridiem(self) -> None:
        for hour24 in range(24):
            moment = datetime(2025, 12, 12, hour24, 10, 34)
            twelve = moment.strftime("%I:%M:%S")
            for meridiem in (moment.strftime("%p"), moment.strftime("%p").lower()):
                text = f"2025-12-12 {twelve} {meridiem}"
                with self.subTest(text=text):
                    result = self.assertSingleDate(
                        text, moment.strftime("%Y-%m-%d %H:%M:%S"), "yyyy-MM-dd hh:mm:ss a"
                    )
                    self.assertEqual(result.con_date_format, "yyyy-MM-dd HH:mm:ss")

    def test_with_milliseconds(self) -> None:
        self.runCases(
            [
                ("2025-12-12 12:00:00.500 AM", "2025-12-12 00:00:00.500", "yyyy-MM-dd hh:mm:ss.SSS a"),
                ("2025-12-12 12:00:00.500 PM", "2025-12-12 12:00:00.500", "yyyy-MM-dd hh:mm:ss.SSS a"),
                ("2025-12-12 02:10:34.235 PM", "2025-12-12 14:10:34.235", "yyyy-MM-dd hh:mm:ss.SSS a"),
            ]
        )

    def test_out_of_range_12_hour_keeps_date_only(self) -> None:
        self.runCases(
            [
                ("2025-12-12 13:10:34 PM", "2025-12-12", "yyyy-MM-dd"),
                ("2025-12-12 00:10:34 AM", "2025-12-12", "yyyy-MM-dd"),
            ]
        )


# ---------------------------------------------------------------------------
# Dates inside running text
# ---------------------------------------------------------------------------


class TestDatesInText(ParserTestCase):
    def test_surrounding_text(self) -> None:
        self.runCases(
            [
                ("Date of Birth: 09/08/25", "2025-09-08", "MM/dd/yy"),
                ("Date of Birth:07/04/2026Address", "2026-07-04", "MM/dd/yyyy"),
                ("Invoice dated 2025-03-14 is overdue", "2025-03-14", "yyyy-MM-dd"),
                ("(12/12/2025)", "2025-12-12", "MM/dd/yyyy"),
                ("Meeting on December 12, 2025 at noon", "2025-12-12", "MMMMM dd, yyyy"),
                ("Shipped 2025-12-12 10:20:30 via courier", "2025-12-12 10:20:30", "yyyy-MM-dd HH:mm:ss"),
                ("due:12/31/2025;", "2025-12-31", "MM/dd/yyyy"),
            ]
        )

    def test_date_at_end_of_sentence(self) -> None:
        self.assertSingleDate("The deadline is 12/31/2025.", "2025-12-31")

    def test_multiple_dates(self) -> None:
        text = "From 2025-01-15 to 02/20/2025, then March 3, 2025 and 2025-04-04 08:00:00."
        values = [r.date_time_string for r in parse(text)]
        self.assertEqual(values, ["2025-01-15", "2025-02-20", "2025-03-03", "2025-04-04 08:00:00"])

    def test_multiline(self) -> None:
        text = "line one 2025-01-01\nline two 12/25/2025\n\tline three 1 Jan 2026\n"
        values = [r.date_time_string for r in parse(text)]
        self.assertEqual(values, ["2025-01-01", "2025-12-25", "2026-01-01"])

    def test_positions(self) -> None:
        # start/end are 0-based and inclusive: text[start:end + 1] is the matched date.
        for text, span in (
            ("2025-03-14", "2025-03-14"),
            ("x 2025-03-14", "2025-03-14"),
            ("Invoice dated 2025-03-14 is overdue", "2025-03-14"),
            ("x 12/12/2025 y", "12/12/2025"),
            ("Date of Birth:07/04/2026Address", "07/04/2026"),
            ("on 12 Dec 2025", "12 Dec 2025"),
            ("x 12 Dec 2025 y", "12 Dec 2025"),
            ("x 12  Dec 2025 y", "12  Dec 2025"),
            ("x 2025 15 Dec y", "2025 15 Dec"),
            ("x 2025 15 Dec", "2025 15 Dec"),
            ("x SEPTEMBER 15, 2025 y", "SEPTEMBER 15, 2025"),
            ("at 2025-12-12 10:20:30", "2025-12-12 10:20:30"),
            ("at 2025-12-12 10:20:30 sharp", "2025-12-12 10:20:30"),
            ("at 2025-12-12T10:20:30 sharp", "2025-12-12T10:20:30"),
            ("at 2025-12-12 10:20:30.123 sharp", "2025-12-12 10:20:30.123"),
            ("at 2025-12-12 10:20:30. Next", "2025-12-12 10:20:30"),
            ("at 2025-12-12 10:20:30 PM sharp", "2025-12-12 10:20:30 PM"),
            ("at 2025-12-12 10:20:30 PM", "2025-12-12 10:20:30 PM"),
        ):
            with self.subTest(text=text):
                (result,) = parse(text)
                self.assertEqual(text[result.start : result.end + 1], span)
                self.assertEqual(result.start, text.index(span))

    def test_positions_with_multiple_dates(self) -> None:
        text = "From 2025-01-15 to 02/20/2025, then March 3, 2025 and 2025-04-04 08:00:00."
        spans = [text[r.start : r.end + 1] for r in parse(text)]
        self.assertEqual(spans, ["2025-01-15", "02/20/2025", "March 3, 2025", "2025-04-04 08:00:00"])


class TestNotDates(ParserTestCase):
    def test_non_date_text(self) -> None:
        for text in (
            "",
            "hello world",
            "no dates here at all",
            "12345678",
            "version 1.2.3",
            "call 555-1234",
            "2025",
            "12/12",
            "Dec 2025",
            "May I help you?",
            "march forward",
        ):
            with self.subTest(text=text):
                self.assertNoDate(text)


if __name__ == "__main__":
    unittest.main()
