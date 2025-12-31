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
            if element.hasAmPm:
                found_format = f"{found_format} a"
            localdate.identified_date_format = found_format
            date_groups.append(localdate)
        return date_groups

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
                    present_format = "yy$" if year < 99 else "yyyy$"
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
                if year > 31:
                    present_format = "yy" if year < 99 else "yyyy"
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
        return None

    def putTimeInDate(self, localdate: LocalDateModel, element: DateElement) -> LocalDateModel:
        format_string = "HH:mm:ss"
        s = element.timeFragment or ""
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
            if "pm" in s.lower():
                hour = hour + 12
                probable_time_format = f"{probable_time_format}"
            format_string = format_string.replace("HH", "hh")
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
                if 9 < pYear < 100:
                    local_date.identified_date_format = "dd$MM&yy"
                if 99 < pYear < 10000:
                    local_date.identified_date_format = "dd$MM&yyyy"
                return local_date
        if d2 > 12 and 0 < d1 <= 12:
            p_date = d2
            p_month = d1
            local_date = self.getYyyyMmDdProbable(pYear, p_month, p_date)
            if local_date:
                if 9 < pYear < 100:
                    local_date.identified_date_format = "MM$dd&yy"
                if 99 < pYear < 10000:
                    local_date.identified_date_format = "MM$dd&yyyy"
                return local_date
        if d1 <= 12 and d2 <= 12:
            p_month = d1
            p_date = d2
            local_date = self.getYyyyMmDdProbable(pYear, p_month, p_date)
            if local_date:
                if 9 < pYear < 100:
                    local_date.identified_date_format = "MM$dd&yy"
                if 99 < pYear < 10000:
                    local_date.identified_date_format = "MM$dd&yyyy"
                return local_date
        return None

    def getYyMmDdProbable(self, pYear: int, pMonth: int, pDay: int) -> Optional[LocalDateModel]:
        return self.getYyyyMmDdProbable(pYear, pMonth, pDay)

    def getYyyyMmDdProbable(self, pYear: int, pMonth: int, pDay: int) -> Optional[LocalDateModel]:
        year = pYear
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
            if year % 4 > 0 and pDay < 29:
                day = pDay
            elif year % 4 == 0 and pDay < 30:
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
        localdate.date_time_string = f"{year:04d}-{month:02d}-{day:02d}"
        localdate.con_date_format = "yyyy-MM-dd"
        if 9 < year < 100:
            format_probable = "yy$" + format_probable
        if 999 < year < 10000:
            format_probable = "yyyy$" + format_probable
        localdate.identified_date_format = format_probable
        return localdate

    def getDateGroups(self, text: str) -> Optional[List[DateElement]]:
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
        tree = Dictionary.patternPredictionTree
        month = Dictionary.monthPredictionTree
        time = Dictionary.timePredictionTree
        text_length = len(text)
        for count in range(text_length):
            c = text[count]
            if i == 0:
                tree = Dictionary.patternPredictionTree
                is_alphanumeric = False
            if i > 1 and possible_date[i - 1] == " " and c == " ":
                whitespace_count += 1
                continue
            if search_for_time_piece:
                time_determined = time.explict_date_fragment
                if time_frg_length > 12 and possible_time[time_frg_length - 1] == " ":
                    time_determined = True
                if Helper.isDigit(c):
                    time = time.get_child("D")
                else:
                    time = time.get_child(c.lower())
                if time is None:
                    if time_determined:
                        date_groups = self.addTimeFragment(
                            date_groups, possible_date, possible_time, count, i, time_frg_length, date_time_separator
                        )
                    if time_frg_length > 0 and self.isValidTimeFragmentWithEndingDelim(possible_time):
                        possible_time[time_frg_length - 1] = " "
                        if i > 0:
                            possible_date[i - 1] = " "
                        date_groups = self.addTimeFragment(
                            date_groups, possible_date, possible_time, count, i - 1, time_frg_length, date_time_separator
                        )
                    search_for_time_piece = False
                    possible_date = self.nullifyBuffer(possible_date)
                    possible_time = self.nullifyBuffer(possible_time)
                    end_found_earlier = False
                    time = Dictionary.timePredictionTree
                    i = 0
                    whitespace_count = 0
                    time_frg_length = 0
                    continue
                else:
                    if time_determined:
                        if count == text_length - 1:
                            date_groups = self.addTimeFragment(
                                date_groups, possible_date, possible_time, count, i, time_frg_length, date_time_separator
                            )
                            search_for_time_piece = False
                            possible_date = self.nullifyBuffer(possible_date)
                            possible_time = self.nullifyBuffer(possible_time)
                            end_found_earlier = False
                            time = Dictionary.timePredictionTree
                            i = 0
                            whitespace_count = 0
                            time_frg_length = 0
                            continue
                        if c == " ":
                            try:
                                next_chars = text[count + 1 : count + 3]
                                if next_chars.lower() in {"am", "pm"}:
                                    possible_time[time_frg_length] = c
                                    time_frg_length += 1
                                    possible_date[i] = c
                                    i += 1

                                    possible_time[time_frg_length] = text[count + 1]
                                    time_frg_length += 1
                                    possible_date[i] = text[count + 1]
                                    i += 1

                                    possible_time[time_frg_length] = text[count + 2]
                                    time_frg_length += 1
                                    possible_date[i] = text[count + 2]
                                    i += 1
                            except IndexError:
                                pass
                            date_groups = self.addTimeFragment(
                                date_groups, possible_date, possible_time, count, i, time_frg_length, date_time_separator
                            )
                            search_for_time_piece = False
                            possible_date = self.nullifyBuffer(possible_date)
                            possible_time = self.nullifyBuffer(possible_time)
                            end_found_earlier = False
                            time = Dictionary.timePredictionTree
                            i = 0
                            whitespace_count = 0
                            time_frg_length = 0
                            continue
                    else:
                        if count == text_length - 1 and time.explict_date_fragment:
                            if Helper.isDigit(c):
                                possible_time[time_frg_length] = c
                                time_frg_length += 1
                                possible_date[i] = c
                                i += 1
                            date_groups = self.addTimeFragment(
                                date_groups, possible_date, possible_time, count, i, time_frg_length, date_time_separator
                            )
                            search_for_time_piece = False
                            possible_date = self.nullifyBuffer(possible_date)
                            possible_time = self.nullifyBuffer(possible_time)
                            end_found_earlier = False
                            time = Dictionary.timePredictionTree
                            i = 0
                            whitespace_count = 0
                            time_frg_length = 0
                            continue
                    possible_time[time_frg_length] = c
                    time_frg_length += 1
                    possible_date[i] = c
                    i += 1
                continue
            if Helper.isDigit(c) or Helper.isDelimeter(c) or Helper.isTimeSeprator(c):
                if marker == "M":
                    if month_determined:
                        is_alphanumeric = True
                        tree = tree.get_child(marker)
                        if tree is None and end_found_earlier:
                            continue
                    else:
                        tree = Dictionary.patternPredictionTree
                        possible_date = self.nullifyBuffer(possible_date)
                        i = 0
                        whitespace_count = 0
                        end_found_earlier = False
                    month = Dictionary.monthPredictionTree
                marker = "D" if Helper.isDigit(c) else "*"
                if tree is None:
                    if end_found_earlier:
                        date_groups = self.addDateFragment(
                            date_groups, possible_date, count, time_frg_length + i + whitespace_count, is_alphanumeric
                        )
                        is_alphanumeric = False
                        if Helper.isDigit(c):
                            time = time.get_child("D")
                            if time is not None:
                                possible_time[time_frg_length] = c
                                time_frg_length += 1
                                search_for_time_piece = True
                                possible_date[i] = c
                                i += 1
                            else:
                                possible_date = self.nullifyBuffer(possible_date)
                                i = 0
                                whitespace_count = 0
                                end_found_earlier = False
                        else:
                            possible_date = self.nullifyBuffer(possible_date)
                            i = 0
                            whitespace_count = 0
                            end_found_earlier = False
                        end_found_earlier = False
                        tree = Dictionary.patternPredictionTree
                        month = Dictionary.monthPredictionTree
                        continue
                    else:
                        possible_date = self.nullifyBuffer(possible_date)
                        i = 0
                        whitespace_count = 0
                        end_found_earlier = False
                        tree = Dictionary.patternPredictionTree
                        month = Dictionary.monthPredictionTree
                        continue
                tree = tree.get_child(marker)
                if tree is None:
                    if end_found_earlier:
                        date_groups = self.addDateFragment(
                            date_groups, possible_date, count, time_frg_length + i + whitespace_count, is_alphanumeric
                        )
                        end_found_earlier = False
                        is_alphanumeric = False
                        if Helper.isTimeSeprator(c):
                            search_for_time_piece = True
                            possible_date[i] = c
                            i += 1
                            date_time_separator = c
                        else:
                            possible_date = self.nullifyBuffer(possible_date)
                            i = 0
                            whitespace_count = 0
                        tree = Dictionary.patternPredictionTree
                        month = Dictionary.monthPredictionTree
                    continue
                else:
                    possible_date[i] = c
                    i += 1
                    end_found_earlier = tree.explict_date_fragment
                    if count == text_length - 1 and end_found_earlier:
                        date_groups = self.addDateFragment(
                            date_groups, possible_date, count, time_frg_length + i + whitespace_count, is_alphanumeric
                        )
                        is_alphanumeric = False
                        break
            else:
                marker = "M"
                c_lower = c.lower()
                month = month.get_child(c_lower)
                if month is None:
                    if end_found_earlier:
                        date_groups = self.addDateFragment(
                            date_groups, possible_date, count, time_frg_length + i + whitespace_count, is_alphanumeric
                        )
                        is_alphanumeric = False
                        end_found_earlier = False
                    possible_date = self.nullifyBuffer(possible_date)
                    i = 0
                    whitespace_count = 0
                    month = Dictionary.monthPredictionTree
                    tree = Dictionary.patternPredictionTree
                    month_determined = False
                    end_found_earlier = False
                    continue
                else:
                    month_determined = month.explict_date_fragment
                    possible_date[i] = c_lower
                    i += 1
        return date_groups

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
        count: int,
        i: int,
        time_frg_length: int,
        date_time_separator: str,
    ) -> Optional[List[DateElement]]:
        if not date_groups:
            return date_groups
        ele = date_groups[-1]
        ele.data = self._buffer_to_string(possible_date)
        ele.endPos = count
        ele.timeFragment = self._buffer_to_string(possible_time)
        if time_frg_length >= 2:
            ampm = f"{possible_time[time_frg_length - 2]}{possible_time[time_frg_length - 1]}"
            if ampm.lower() in {"am", "pm"}:
                ele.hasAmPm = True
                ele.endPos = count + 3
        ele.dateTimeSeprator = date_time_separator
        return date_groups

    def createDateFragment(
        self, buffer: List[str], position: int, length: int, is_alphanumeric: bool
    ) -> Optional[DateElement]:
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
