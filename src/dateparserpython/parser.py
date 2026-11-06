from __future__ import annotations

import re
from typing import Iterable, List, Optional

try:
    from . import dictionary as Dictionary
    from . import helper as Helper
    from .models import DateElement, LocalDateModel
except ImportError:  # pragma: no cover - fallback for direct module execution
    from dateparserpython import dictionary as Dictionary
    from dateparserpython import helper as Helper
    from dateparserpython.models import DateElement, LocalDateModel


class Parser:
    """
    Python port of the Java Parser class. The public API mirrors the Java
    version: call parse(text) to receive a list of LocalDateModel instances.
    """

    def __init__(self) -> None:
        self.delim = "-.\\/|:, "
        self.learnedPatternString: Optional[str] = None
        self.learnPattern = False
        self._tokenizer_cache: dict[str, re.Pattern[str]] = {}

    def parse(self, text: str) -> List[LocalDateModel]:
        date_groups: List[LocalDateModel] = []
        groups = self.getDateGroups(text)
        if not groups:
            return date_groups
        for element in groups:
            if not self._isPlausible(text, element):
                continue
            localdate = self.getDateFromPhrase(element)
            if localdate is None:
                continue
            localdate.start = element.startPos
            localdate.end = element.endPos
            if element.timeFragment:
                localdate = self.putTimeInDate(localdate, element)
            date_fragment = element.getDateFragment() or ""
            delims = re.sub(r"[A-Za-z0-9]", "", date_fragment)
            found_format = localdate.identified_date_format or ""
            if len(delims) == 2:
                found_format = found_format.replace("$", delims[0])
                found_format = found_format.replace("&", delims[1])
            if len(delims) == 3:
                found_format = found_format.replace("$", delims[0])
                found_format = found_format.replace("&", delims[1] + delims[2])
            if element.isAlphaNumeric and Helper.isFullMonth(element.data):
                found_format = found_format.replace("MMM", "MMMMM")
            if element.hasAmPm and "hh" in found_format:
                found_format = f"{found_format}{element.amPmSeparator}a"
            localdate.identified_date_format = found_format
            date_groups.append(localdate)
        return date_groups

    # Separators accepted between the fields of an all-numeric date. Comma and colon are left
    # out: "3,4,25" is a list and "10:30:45" is a time.
    NUMERIC_DATE_SEPARATORS = "/-. \\"
    MAX_YEAR = 2999

    def _isPlausible(self, text: str, element: DateElement) -> bool:
        """Reject pattern matches that are almost never dates in real text."""
        fragment = element.getDateFragment() or ""
        tokens = re.findall(r"[0-9]+|[a-z]+", fragment.lower())
        separators = re.findall(r"[^0-9A-Za-z]+", fragment)
        if len(tokens) < 3 or len(separators) < 2:
            return False
        if any(len(t) == 4 and t.isdigit() and int(t) > self.MAX_YEAR for t in tokens):
            return False
        first, second = separators[0], separators[1]
        if element.isAlphaNumeric:
            if first == "," and second != ",":
                return False  # "12,Dec 2025"; all-comma forms like "2025,01,Jan" are fine
            if len(first) == len(second) == 1 and first != second and second != ",":
                return False  # "12-Dec/2025"; "Dec 12,2025" is still fine
            if tokens[0].isalpha() and len(tokens[2]) == 2 and "," not in second:
                return False  # "May 12 13 people"; "Dec 12, 25" is still fine
            return True
        if first != second or len(first) != 1 or first not in self.NUMERIC_DATE_SEPARATORS:
            return False  # mixed ("2025/12-12") or unsupported separators
        year = tokens[0] if len(tokens[0]) == 4 or int(tokens[0]) > 31 else tokens[2]
        if first == " " and len(year) != 4:
            return False  # "8 9 10" in "qty 7 8 9 10"
        if first == "." and len(year) == 2 and any(len(t) == 1 for t in tokens):
            return False  # version numbers like "3.10.12"; "01.02.25" is still fine
        # Part of a longer chain like "1.2.3.2024" or "12/12/2025/1".
        start = element.startPos
        if start >= 2 and text[start - 1] == first and text[start - 2].isdigit():
            return False
        end = element.endPos
        if element.timeFragment is None and end + 2 < len(text) and text[end + 1] == first and text[end + 2].isdigit():
            return False
        return True

    def _tokenize(self, text: str, delimiters: str) -> List[str]:
        if delimiters not in self._tokenizer_cache:
            pattern = "[" + re.escape(delimiters) + "]+"
            self._tokenizer_cache[delimiters] = re.compile(pattern)
        return [token for token in self._tokenizer_cache[delimiters].split(text) if token]

    def getDateFromPhrase(self, element: DateElement) -> Optional[LocalDateModel]:
        if element.timeFragment is None:
            s = element.data
        else:
            s = element.dateFragment or element.data
        if element.isAlphaNumeric:
            tokens = self._tokenize(s, self.delim)
            if len(tokens) < 3:
                return None
            t1, t2, t3 = tokens[:3]
            if Helper.isDigit(t1):
                year = int(t1)
                if year > 31:
                    present_format = "yy$" if year < 100 else "yyyy$"
                    if Helper.isDigit(t2):
                        present_format = present_format + "dd&MMM"
                        day = int(t2)
                        month = self.monthToDigit(t3)
                    else:
                        present_format = present_format + "MMM&dd"
                        month = self.monthToDigit(t2)
                        day = int(t3)
                    local_date = self.getYyyyMmDdProbable(year, month, day)
                    if local_date:
                        local_date.original_text = element.data
                        local_date.identified_date_format = present_format
                        return local_date
            if Helper.isDigit(t3):
                year = int(t3)
                # A trailing two-digit value is the year even when it could be a day ("12 Dec 25").
                if year > 31 or len(t3) == 2:
                    present_format = "yy" if year < 100 else "yyyy"
                    if Helper.isDigit(t1):
                        present_format = f"dd$MMM&{present_format}"
                        day = int(t1)
                        month = self.monthToDigit(t2)
                    else:
                        present_format = f"MMM$dd&{present_format}"
                        month = self.monthToDigit(t1)
                        day = int(t2)
                    local_date = self.getYyyyMmDdProbable(year, month, day)
                    if local_date:
                        local_date.original_text = element.data
                        local_date.identified_date_format = present_format
                        return local_date
            return None
        else:
            if "T" in s or "_" in s:
                return None
            tokens = self._tokenize(s, self.delim)
            if len(tokens) < 3:
                return None
            d1, d2, d3 = (int(token) for token in tokens[:3])
            if d1 > 999:
                local_date = self.getYyyyMmDdProbable(d1, d2, d3)
                if local_date:
                    local_date.original_text = element.data
                    if self.learnPattern and self.learnedPatternString is not None:
                        self.learnedPatternString = local_date.con_date_format
                    return local_date
            if 31 < d1 < 100:
                local_date = self.getYyMmDdProbable(d1, d2, d3)
                if local_date:
                    local_date.original_text = element.data
                    if self.learnPattern and self.learnedPatternString is not None:
                        self.learnedPatternString = local_date.con_date_format
                    return local_date
            if d3 > 999 and ((0 < d1 < 32) or (0 < d2 < 32)) and d1 > 0 and d2 > 0:
                local_date = self.getDetemintaionForYyyyPrefix(d1, d2, d3)
                if local_date:
                    local_date.original_text = element.data
                    if self.learnPattern and self.learnedPatternString is not None:
                        self.learnedPatternString = local_date.con_date_format
                    return local_date
            if 31 < d3 < 100 and ((0 < d1 < 32) or (0 < d2 < 32)):
                local_date = self.getDetemintaionForYyyyPrefix(d1, d2, d3)
                if local_date:
                    local_date.original_text = element.data
                    if self.learnPattern and self.learnedPatternString is not None:
                        self.learnedPatternString = local_date.con_date_format
                    return local_date
            # Two-digit year that is also a valid day/month (e.g. "12/12/25"): assume year-last.
            if len(tokens[2]) == 2 and d3 <= 31 and 0 < d1 < 32 and 0 < d2 < 32:
                local_date = self.getDetemintaionForYyyyPrefix(d1, d2, d3)
                if local_date:
                    local_date.original_text = element.data
                    if self.learnPattern and self.learnedPatternString is not None:
                        self.learnedPatternString = local_date.con_date_format
                    return local_date
        return None

    def putTimeInDate(self, localdate: LocalDateModel, element: DateElement) -> LocalDateModel:
        format_string = "HH:mm:ss"
        s = element.timeFragment or ""
        meridiem = ""
        if element.hasAmPm:
            meridiem = s[-2:].lower()
            s = s[:-2].rstrip()
        probable_time_format = format_string
        tokens: Iterable[str]
        if "." in s or "," in s:
            tokens = self._tokenize(s, ":., ")
            hour, minute, second, millis = (int(token) for token in tokens[:4])
            if "." in s:
                probable_time_format = format_string + ".SSS"
            if "," in s:
                probable_time_format = format_string + ",SSS"
        else:
            tokens = self._tokenize(s, ": ")
            hour, minute, second = (int(token) for token in tokens[:3])
            millis = 0
        if element.hasAmPm:
            if not 0 < hour <= 12:
                return localdate
            # 12 AM is midnight (00), 12 PM is noon (12).
            if meridiem == "pm":
                hour = hour % 12 + 12
            else:
                hour = hour % 12
            probable_time_format = probable_time_format.replace("HH", "hh")
        if hour < 24 and minute < 60 and second < 60 and millis < 10000:
            time_piece = f"{hour:02d}:{minute:02d}:{second:02d}"
            if millis >= 0 and ("." in s or "," in s):
                time_piece = f"{time_piece}.{millis:03d}"
            localdate.con_date_format = f"{localdate.con_date_format} {format_string}"
            localdate.date_time_string = f"{localdate.date_time_string} {time_piece}"
            sep = "'T'" if element.dateTimeSeprator == "T" else element.dateTimeSeprator
            identified = localdate.identified_date_format or ""
            localdate.identified_date_format = f"{identified}{sep}{probable_time_format}"
        return localdate

    def getDetemintaionForYyPrefix(self, d1: int, d2: int, pYear: int) -> Optional[LocalDateModel]:
        return self.getDetemintaionForYyyyPrefix(d1, d2, pYear)

    def getDetemintaionForYyyyPrefix(self, d1: int, d2: int, pYear: int) -> Optional[LocalDateModel]:
        if d1 > 12 and 0 < d2 <= 12:
            p_date = d1
            p_month = d2
            local_date = self.getYyyyMmDdProbable(pYear, p_month, p_date)
            if local_date:
                if 0 <= pYear < 100:
                    local_date.identified_date_format = "dd$MM&yy"
                if 99 < pYear < 10000:
                    local_date.identified_date_format = "dd$MM&yyyy"
                return local_date
        if d2 > 12 and 0 < d1 <= 12:
            p_date = d2
            p_month = d1
            local_date = self.getYyyyMmDdProbable(pYear, p_month, p_date)
            if local_date:
                if 0 <= pYear < 100:
                    local_date.identified_date_format = "MM$dd&yy"
                if 99 < pYear < 10000:
                    local_date.identified_date_format = "MM$dd&yyyy"
                return local_date
        if d1 <= 12 and d2 <= 12:
            p_month = d1
            p_date = d2
            local_date = self.getYyyyMmDdProbable(pYear, p_month, p_date)
            if local_date:
                if 0 <= pYear < 100:
                    local_date.identified_date_format = "MM$dd&yy"
                if 99 < pYear < 10000:
                    local_date.identified_date_format = "MM$dd&yyyy"
                return local_date
        return None

    def getYyMmDdProbable(self, pYear: int, pMonth: int, pDay: int) -> Optional[LocalDateModel]:
        return self.getYyyyMmDdProbable(pYear, pMonth, pDay)

    def getYyyyMmDdProbable(self, pYear: int, pMonth: int, pDay: int) -> Optional[LocalDateModel]:
        year = pYear
        full_year = self.expandTwoDigitYear(year)
        month = -100
        day = -100
        format_probable = ""
        if 0 < pMonth < 13:
            month = pMonth
            format_probable = "MM&dd"
        elif pMonth > 12 and pDay < 13:
            month = pDay
            pDay = pMonth
            format_probable = "dd&MM"
        else:
            return None
        if month == 2:
            if pDay < (30 if self.isLeapYear(full_year) else 29):
                day = pDay
            else:
                return None
        elif self.is31DayMonth(month):
            if pDay < 32:
                day = pDay
            else:
                return None
        elif self.is30DayMonth(month):
            if pDay < 31:
                day = pDay
            else:
                return None
        else:
            return None
        localdate = LocalDateModel()
        localdate.date_time_string = f"{full_year:04d}-{month:02d}-{day:02d}"
        localdate.con_date_format = "yyyy-MM-dd"
        if 9 < year < 100:
            format_probable = "yy$" + format_probable
        if 999 < year < 10000:
            format_probable = "yyyy$" + format_probable
        localdate.identified_date_format = format_probable
        return localdate

    def expandTwoDigitYear(self, year: int) -> int:
        """Pivot two-digit years like strptime's %y: 00-68 -> 20xx, 69-99 -> 19xx."""
        if 0 <= year < 100:
            return year + (2000 if year < 69 else 1900)
        return year

    def getDateGroups(self, text: str) -> Optional[List[DateElement]]:
        groups = self._scanDateGroups(text)
        if not groups:
            return groups
        resolved: List[DateElement] = []
        for group in groups:
            if resolved and group.startPos <= resolved[-1].endPos:
                continue  # swallowed by a longer match chosen for the previous group
            resolved.append(self._preferLaterMatch(text, group))
        return resolved

    def _scanDateGroups(self, text: str) -> Optional[List[DateElement]]:
        date_groups: Optional[List[DateElement]] = None
        possible_date = ["\x00"] * 30
        possible_time = ["\x00"] * 17
        i = 0
        end_found_earlier = False
        month_determined = False
        search_for_time_piece = False
        time_frg_length = 0
        marker = "0"
        is_alphanumeric = False
        date_time_separator = " "
        whitespace_count = 0
        candidate_start = 0
        time_start = 0
        tree = Dictionary.patternPredictionTree
        month = Dictionary.monthPredictionTree
        time = Dictionary.timePredictionTree
        text_length = len(text)
        # When a candidate dies, restart_at is set and the scan resumes there with a clean state,
        # so characters a failed candidate consumed (e.g. the "1" in "Entry 1: 2024/07/04") can't
        # hide a date that starts later.
        restart_at: Optional[int] = None
        count = -1
        while True:
            if restart_at is not None:
                count = restart_at
                restart_at = None
                possible_date = self.nullifyBuffer(possible_date)
                possible_time = self.nullifyBuffer(possible_time)
                i = 0
                whitespace_count = 0
                time_frg_length = 0
                end_found_earlier = False
                month_determined = False
                search_for_time_piece = False
                is_alphanumeric = False
                marker = "0"
                tree = Dictionary.patternPredictionTree
                month = Dictionary.monthPredictionTree
                time = Dictionary.timePredictionTree
            else:
                count += 1
            if count >= text_length:
                break
            c = text[count]
            if i == 0:
                tree = Dictionary.patternPredictionTree
                is_alphanumeric = False
                candidate_start = count
            if i > 1 and possible_date[i - 1] == " " and c == " ":
                whitespace_count += 1
                continue
            if search_for_time_piece:
                time_determined = time.explict_date_fragment
                if time_frg_length > 12 and possible_time[time_frg_length - 1] == " ":
                    time_determined = True
                next_time = time.get_child("D" if Helper.isDigit(c) else c.lower())
                if next_time is None:
                    if time_determined and self._meridiemAt(text, count):
                        # Meridiem written straight after the time: "10:20:30PM".
                        for ch in text[count : count + 2]:
                            possible_time[time_frg_length] = ch
                            time_frg_length += 1
                            possible_date[i] = ch
                            i += 1
                        date_groups = self.addTimeFragment(
                            date_groups, possible_date, possible_time, count + 1, i, time_frg_length, date_time_separator
                        )
                        restart_at = count + 2
                    elif time_determined:
                        date_groups = self.addTimeFragment(
                            date_groups, possible_date, possible_time, count - 1, i, time_frg_length, date_time_separator
                        )
                        restart_at = count
                    elif time_frg_length > 0 and self.isValidTimeFragmentWithEndingDelim(possible_time):
                        possible_time[time_frg_length - 1] = " "
                        if i > 0:
                            possible_date[i - 1] = " "
                        date_groups = self.addTimeFragment(
                            date_groups, possible_date, possible_time, count - 2, i - 1, time_frg_length, date_time_separator
                        )
                        restart_at = count
                    else:
                        # Not a time after all; rescan those characters as possible dates.
                        restart_at = time_start
                    continue
                time = next_time
                if time_determined:
                    if count == text_length - 1:
                        date_groups = self.addTimeFragment(
                            date_groups, possible_date, possible_time, count - 1, i, time_frg_length, date_time_separator
                        )
                        break
                    if c == " ":
                        time_end = count - 1
                        if self._meridiemAt(text, count + 1):
                            for ch in text[count : count + 3]:
                                possible_time[time_frg_length] = ch
                                time_frg_length += 1
                                possible_date[i] = ch
                                i += 1
                            time_end = count + 2
                        date_groups = self.addTimeFragment(
                            date_groups, possible_date, possible_time, time_end, i, time_frg_length, date_time_separator
                        )
                        restart_at = time_end + 1
                        continue
                elif count == text_length - 1 and time.explict_date_fragment:
                    time_end = count - 1
                    if Helper.isDigit(c):
                        possible_time[time_frg_length] = c
                        time_frg_length += 1
                        possible_date[i] = c
                        i += 1
                        time_end = count
                    date_groups = self.addTimeFragment(
                        date_groups, possible_date, possible_time, time_end, i, time_frg_length, date_time_separator
                    )
                    break
                possible_time[time_frg_length] = c
                time_frg_length += 1
                possible_date[i] = c
                i += 1
                continue
            # "T" separates date and time only between digits (2025-12-12T10:00:00);
            # anywhere else it is a letter, e.g. in "OCT" or "AUGUST".
            is_iso_t = (
                c == "T" and 0 < count < text_length - 1 and text[count - 1].isdigit() and text[count + 1].isdigit()
            )
            if Helper.isDigit(c) or Helper.isDelimeter(c) or (Helper.isTimeSeprator(c) and (c != "T" or is_iso_t)):
                if marker == "M":
                    if month_determined:
                        is_alphanumeric = True
                        tree = tree.get_child(marker)
                        if tree is None:
                            restart_at = self._nextTokenStart(text, candidate_start)
                            continue
                        # Patterns such as yyyy-dd-MMM end on the month itself.
                        end_found_earlier = tree.explict_date_fragment
                    else:
                        # A partial month name ("Ma") followed by a digit/delimiter: start over at c.
                        tree = Dictionary.patternPredictionTree
                        possible_date = self.nullifyBuffer(possible_date)
                        i = 0
                        whitespace_count = 0
                        end_found_earlier = False
                        candidate_start = count
                    month = Dictionary.monthPredictionTree
                marker = "D" if Helper.isDigit(c) else "*"
                next_tree = tree.get_child(marker)
                if next_tree is None:
                    if not end_found_earlier:
                        restart_at = self._nextTokenStart(text, candidate_start)
                        continue
                    date_groups = self.addDateFragment(
                        date_groups, possible_date, count - 1, time_frg_length + i + whitespace_count, is_alphanumeric
                    )
                    end_found_earlier = False
                    is_alphanumeric = False
                    if Helper.isTimeSeprator(c):
                        search_for_time_piece = True
                        possible_date[i] = c
                        i += 1
                        date_time_separator = c
                        time_start = count + 1
                        tree = Dictionary.patternPredictionTree
                        month = Dictionary.monthPredictionTree
                    else:
                        restart_at = count
                    continue
                tree = next_tree
                possible_date[i] = c
                i += 1
                end_found_earlier = tree.explict_date_fragment
                if count == text_length - 1 and end_found_earlier:
                    date_groups = self.addDateFragment(
                        date_groups, possible_date, count, time_frg_length + i + whitespace_count, is_alphanumeric
                    )
                    break
            else:
                # A complete date immediately followed by a letter (e.g. "07/04/2026Address"):
                # no pattern continues a finished date with a month, so close it out first.
                if end_found_earlier:
                    date_groups = self.addDateFragment(
                        date_groups, possible_date, count - 1, time_frg_length + i + whitespace_count, is_alphanumeric
                    )
                    restart_at = count
                    continue
                marker = "M"
                c_lower = c.lower()
                next_month = month.get_child(c_lower)
                if next_month is None:
                    # A date ending on its month ("2025 15 Dec") closed by punctuation or a newline.
                    if month_determined and not c.isalpha() and self._endsOnMonth(tree):
                        date_groups = self.addDateFragment(
                            date_groups, possible_date, count - 1, i + whitespace_count, True
                        )
                        restart_at = count
                    else:
                        restart_at = self._nextTokenStart(text, candidate_start)
                    continue
                month = next_month
                month_determined = month.explict_date_fragment
                possible_date[i] = c_lower
                i += 1
        # A date ending on its month at the very end of the text ("... 2025 15 Dec").
        if marker == "M" and month_determined and not search_for_time_piece and self._endsOnMonth(tree):
            date_groups = self.addDateFragment(date_groups, possible_date, text_length - 1, i + whitespace_count, True)
        return date_groups

    def _nextTokenStart(self, text: str, position: int) -> int:
        """Index of the first number or word that starts after `position` (len(text) if none)."""
        for j in range(position + 1, len(text)):
            prev, cur = text[j - 1], text[j]
            if (cur.isdigit() and not prev.isdigit()) or (cur.isalpha() and not prev.isalpha()):
                return j
        return len(text)

    def _meridiemAt(self, text: str, position: int) -> bool:
        """True if text has a standalone "am"/"pm" at position (not the start of "amazing")."""
        word = text[position : position + 2]
        after = position + 2
        return word.lower() in {"am", "pm"} and (after >= len(text) or not text[after].isalpha())

    def _preferLaterMatch(self, text: str, group: DateElement) -> DateElement:
        """
        A stray number before a date can form a shorter date of its own: "1 12/12/2025" first
        matches "1 12/12", and "No. 7 December 12, 2025" matches "7 December 12". When such a
        match runs straight into more digits, prefer a valid match starting at its next token
        if that one reaches further.
        """
        while True:
            fragment = group.getDateFragment() or ""
            if group.isAlphaNumeric:
                # Only a trailing two-digit year can really be the day of a longer date.
                if not re.search(r"(?<![0-9])[0-9]{2}$", fragment):
                    break
            else:
                delims = re.sub(r"[0-9]", "", fragment)
                if len(delims) != 2 or delims[0] == delims[1]:
                    break
            after = group.endPos + 1
            while after < len(text) and after <= group.endPos + 2 and Helper.isDelimeter(text[after]):
                after += 1
            if after == group.endPos + 1 or after >= len(text) or not text[after].isdigit():
                break
            later_start = self._nextTokenStart(text, group.startPos)
            if later_start > group.endPos:
                break
            window_end = min(len(text), group.endPos + 64)
            later_groups = self._scanDateGroups(text[later_start:window_end])
            if not later_groups:
                break
            later = later_groups[0]
            if (
                later.startPos != 0
                or later.isAlphaNumeric != group.isAlphaNumeric
                or later_start + later.endPos <= group.endPos
                or (window_end < len(text) and later.endPos >= window_end - later_start - 1)
                or self.getDateFromPhrase(later) is None
            ):
                break
            later_fragment = later.getDateFragment() or ""
            if later.isAlphaNumeric:
                if not re.search(r"[0-9]{4}$", later_fragment):
                    break  # only give up "7 Dec 12" for something firmer, like "Dec 12, 2025"
            else:
                later_delims = re.sub(r"[0-9]", "", later_fragment)
                if len(later_delims) != 2 or later_delims[0] != later_delims[1]:
                    break
            later.startPos += later_start
            later.endPos += later_start
            group = later
        return group

    def _endsOnMonth(self, tree) -> bool:
        if tree is None:
            return False
        node = tree.get_child("M")
        return node is not None and node.explict_date_fragment

    def addDateFragment(
        self,
        date_groups: Optional[List[DateElement]],
        possible_date: List[str],
        count: int,
        pattern_length: int,
        is_alphanumeric: bool,
    ) -> Optional[List[DateElement]]:
        if date_groups is None:
            date_groups = []
        date_element = self.createDateFragment(possible_date, count, pattern_length, is_alphanumeric)
        if date_element is not None:
            date_groups.append(date_element)
        return date_groups

    def isValidTimeFragmentWithEndingDelim(self, possible_time: List[str]) -> bool:
        s = self._buffer_to_string(possible_time)
        original = s
        s = re.sub(r"[0-9]", "", s)
        if 2 < len(s) <= 3:
            if s.startswith("::") and (original.endswith(",") or original.endswith(".")):
                return True
        return False

    def addTimeFragment(
        self,
        date_groups: Optional[List[DateElement]],
        possible_date: List[str],
        possible_time: List[str],
        end: int,
        i: int,
        time_frg_length: int,
        date_time_separator: str,
    ) -> Optional[List[DateElement]]:
        """`end` is the index of the last character of the time, including any AM/PM."""
        if not date_groups:
            return date_groups
        ele = date_groups[-1]
        ele.data = self._buffer_to_string(possible_date)
        ele.endPos = end
        ele.timeFragment = self._buffer_to_string(possible_time)
        if time_frg_length >= 2:
            ampm = f"{possible_time[time_frg_length - 2]}{possible_time[time_frg_length - 1]}"
            if ampm.lower() in {"am", "pm"}:
                ele.hasAmPm = True
                ele.amPmSeparator = " " if time_frg_length >= 3 and possible_time[time_frg_length - 3] == " " else ""
        ele.dateTimeSeprator = date_time_separator
        return date_groups

    def createDateFragment(
        self, buffer: List[str], position: int, length: int, is_alphanumeric: bool
    ) -> Optional[DateElement]:
        """`position` is the index of the date's last character; start/end are inclusive."""
        date_text = self._buffer_to_string(buffer)
        if not date_text:
            return None
        ele = DateElement(date_text)
        length -= 1
        ele.endPos = position
        ele.startPos = position - length
        ele.isAlphaNumeric = is_alphanumeric
        ele.dateFragment = ele.data
        return ele

    def nullifyBuffer(self, buffer: List[str]) -> List[str]:
        for idx in range(len(buffer)):
            buffer[idx] = "\x00"
        return buffer

    def _buffer_to_string(self, buffer: List[str]) -> str:
        return "".join(ch for ch in buffer if ch and ch != "\x00").strip()

    def isLeapYear(self, year: int) -> bool:
        return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

    def is31DayMonth(self, value: int) -> bool:
        return value in {1, 3, 5, 7, 8, 10, 12}

    def is30DayMonth(self, value: int) -> bool:
        return value in {4, 6, 9, 11}

    def monthToDigit(self, text: str) -> int:
        text = text.lower()
        month_map = {
            "jan": 1,
            "january": 1,
            "feb": 2,
            "february": 2,
            "mar": 3,
            "march": 3,
            "apr": 4,
            "april": 4,
            "may": 5,
            "jun": 6,
            "june": 6,
            "jul": 7,
            "july": 7,
            "aug": 8,
            "august": 8,
            "sep": 9,
            "september": 9,
            "oct": 10,
            "october": 10,
            "nov": 11,
            "november": 11,
            "dec": 12,
            "december": 12,
        }
        return month_map.get(text, -1)
