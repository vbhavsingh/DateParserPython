from __future__ import annotations

from typing import List

try:
    from .display import DisplayObject, TreeChar
    from .prediction import PredictionModelNode
except ImportError:
    from display import DisplayObject, TreeChar
    from prediction import PredictionModelNode

monthPredictionTree = PredictionModelNode()
weekPredictionTree = PredictionModelNode()
patternPredictionTree = PredictionModelNode()
timePredictionTree = PredictionModelNode()

WEEKDAY_FULL: List[str] = [
    "sunday",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
]

WEEKDAY_SHORT: List[str] = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]

MONTH_FULL: List[str] = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]

MONTH_SHORT: List[str] = [
    "jan",
    "feb",
    "mar",
    "apr",
    "may",
    "jun",
    "jul",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
]

PATTERN: List[str] = [
    "DDDD*DD*DD",
    "DDDD*D*DD",
    "DDDD*DD*D",
    "DDDD*D*D",
    "DD*DD*DD",
    "DD*D*DD",
    "DD*DD*D",
    "DD*D*D",
    "DD*DD*DDDD",
    "D*DD*DDDD",
    "DD*D*DDDD",
    "D*D*DDDD",
    "DD*DD*DD",
    "D*DD*DD",
    "DD*D*DD",
    "D*D*DD",
    "DDDD*M*DD",
    "DDDD*M*D",
    "DD*M*DD",
    "DD*M*D",
    "DD*M*DDDD",
    "D*M*DDDD",
    "DD*M*DD",
    "D*M*DD",
    "M*DD*DDDD",
    "M*D*DDDD",
    "M*DD*DD",
    "M*D*DD",
    "M*DD**DDDD",
    "M*D**DDDD",
    "M*DD**DD",
    "M*D**DD",
]

TIME_PATTERN: List[str] = [
    "DD:DD:DD",
    "DD:DD:DD ",
    "DD:DD:DD.DDD",
    "DD:DD:DD.DDD ",
    "DD:DD:DD,DDD",
    "DD:DD:DD,DDD ",
    "D:DD:DD",
    "D:DD:DD ",
    "D:DD:DD.DDD",
    "D:DD:DD.DDD ",
    "D:DD:DD,DDD",
    "D:DD:DD,DDD ",
]


MONTH_LITERAL = 1
WEEKDAY_LITERAL = 2
DIGIT_LITERAL = 3
THREE_DIGIT_LITERAL = 4
FOUR_DIGIT_LITERAL = 5
DATE_PHRASE = 6
NOT_DATE_LITERAL = -1

HOROZONTAL_PRINT_GAP = 3
VERTICAL_PRINT_GAP = 2
TERMINATION_SYMBOL = "^"


def buildTree(item_list: List[str], parent_node: PredictionModelNode) -> None:
    for item in item_list:
        parent = parent_node
        parent_node.charcter = "\x00"
        for idx, char in enumerate(item):
            node = parent.get_child(char)
            if node is None:
                child = PredictionModelNode()
                child.charcter = char
                if idx + 1 == len(item):
                    child.explict_date_fragment = True
                parent.add_child(child)
                parent = child
            else:
                if idx + 1 == len(item):
                    node.explict_date_fragment = True
                parent = node


def getProbables(tree: PredictionModelNode) -> str:
    if tree is None:
        return ""
    kids = tree.childern
    pattern = f"{tree.charcter} -->"
    for kid in kids:
        pattern = f"{pattern} {kid.charcter}"
    return pattern


def printTree(tree: PredictionModelNode) -> None:
    tree = sortTree(tree)
    display_object = displayBuilder(DisplayObject(), tree)
    print_buffer: List[str] = []
    line = getBlankLine(display_object.width)
    prev_level = 0
    for tc in display_object.displayBuffer:
        if prev_level == tc.level:
            line = line[: tc.leftSpace] + tc.symbol + line[tc.leftSpace + len(tc.symbol) :]
        else:
            line = line.rstrip() + "\n"
            print_buffer.append(line)
            line = getBlankLine(display_object.width)
            line = line[: tc.leftSpace] + tc.symbol + line[tc.leftSpace + len(tc.symbol) :]
            prev_level = tc.level
    print_buffer.append(line)
    print("".join(print_buffer))


def displayBuilder(display: DisplayObject, tree: PredictionModelNode) -> DisplayObject:
    if isFamilyUnit(tree):
        return familyDisplayBuilder(tree)

    horizontal_display = DisplayObject()
    for kid in tree.childern:
        recursive_display = displayBuilder(horizontal_display, kid)
        horizontal_display = adjustHorizontalDisplay(horizontal_display, recursive_display)

    horizontal_display.displayBuffer.sort()

    vertical_display = DisplayObject()
    dad_joints = [0] * tree.children_count()

    j = 0
    for tc in horizontal_display.displayBuffer:
        if tc.level > 0 or j >= len(dad_joints):
            break
        if tc.symbol not in {"/", "\\", "_", "|"} and tc.symbol.strip():
            dad_joints[j] = tc.leftSpace
            j += 1

    if tree.children_count() == 0:
        return horizontal_display
    if tree.children_count() == 1:
        symbol = f"{tree.charcter}{TERMINATION_SYMBOL}" if tree.explict_date_fragment else f"{tree.charcter}"
        tc = TreeChar(symbol, dad_joints[0], 0)
        vertical_display.displayBuffer.append(tc)
    else:
        dad_joints.sort()
        symbol = "_"
        if len(dad_joints) % 2 == 0:
            papa_position = 1 + (dad_joints[-1] + dad_joints[0]) // 2
        else:
            papa_position = dad_joints[len(dad_joints) // 2] + 1
        papa_position -= 1
        for k in range(dad_joints[0] + 1, dad_joints[-1] + 1 - 2 + 1):
            if k == papa_position:
                s = f"{tree.charcter or '$'}"
                if tree.explict_date_fragment:
                    s = f"{s}{TERMINATION_SYMBOL}"
                tc = TreeChar(s, k, 0)
            else:
                tc = TreeChar(symbol, k, 0)
            vertical_display.displayBuffer.append(tc)

    for joint in dad_joints:
        for m in range(VERTICAL_PRINT_GAP):
            vertical_display.displayBuffer.append(TreeChar("|", joint, m + 1))

    display = adjustVerticalDisplay(horizontal_display, vertical_display)
    return display


def adjustVerticalDisplay(horizontal_display: DisplayObject, vertical_display: DisplayObject) -> DisplayObject:
    if not horizontal_display.displayBuffer:
        return vertical_display
    vertical_display.displayBuffer.sort()
    for tc in horizontal_display.displayBuffer:
        tc.level += VERTICAL_PRINT_GAP + 1
        vertical_display.displayBuffer.append(tc)
    vertical_display.width = horizontal_display.width
    return vertical_display


def adjustHorizontalDisplay(display: DisplayObject, kid_display: DisplayObject) -> DisplayObject:
    if not display.displayBuffer:
        return kid_display

    left_pos = display.width
    for tc in kid_display.displayBuffer:
        tc.leftSpace += left_pos + HOROZONTAL_PRINT_GAP
        inserted = False
        for index, display_tc in enumerate(display.displayBuffer):
            if display_tc.level <= tc.level:
                continue
            display.displayBuffer.insert(max(0, index - 1), tc)
            inserted = True
            break
        if not inserted:
            display.displayBuffer.append(tc)
    display.height = max(display.height, kid_display.height)
    display.width = display.width + kid_display.width + HOROZONTAL_PRINT_GAP
    return display


def familyDisplayBuilder(tree: PredictionModelNode) -> DisplayObject:
    display_object = DisplayObject()
    kids = tree.children_count()
    char_val = f"{tree.charcter}"
    if tree.explict_date_fragment:
        char_val = f"{char_val}{TERMINATION_SYMBOL}"
    if kids == 1:
        display_object.displayBuffer.append(TreeChar(char_val, 0, 0))
        display_object.displayBuffer.append(TreeChar("|", 0, 1))
        kid_char = f"{tree.childern[0].charcter}"
        display_object.displayBuffer.append(TreeChar(kid_char, 0, 2))
        display_object.width = 1
        display_object.height = 3
    elif kids % 2 == 0:
        display_object = evenKidCountTree(display_object, tree)
    else:
        display_object = oddKidCountTree(display_object, tree)
    return display_object


def evenKidCountTree(display_object: DisplayObject, tree: PredictionModelNode) -> DisplayObject:
    kids = tree.children_count()
    papa_position = kids // 2
    char_val = f"{tree.charcter}"
    if tree.explict_date_fragment:
        char_val = f"{char_val}{TERMINATION_SYMBOL}"
    display_object.displayBuffer.append(TreeChar(char_val, papa_position, 0))
    display_object.height = papa_position + 2
    display_object.width = kids + 1
    for i in range(kids // 2):
        markers = (i + 1) * 2
        coeff = 1
        for j in range(markers):
            if coeff == markers // 2 + 1:
                coeff = 1
            if j < markers // 2:
                symbol = "|"
                left_pos = papa_position - coeff
                coeff += 1
                if j == markers // 2 - 1:
                    symbol = "/"
                display_object.displayBuffer.append(TreeChar(symbol, left_pos, i + 1))
            else:
                right_pos = papa_position + coeff
                coeff += 1
                symbol = "|"
                if (j == markers - 1 and i != 0) or markers < 3:
                    symbol = "\\"
                display_object.displayBuffer.append(TreeChar(symbol, right_pos, i + 1))
    for i in range(kids):
        kid_val = f"{tree.childern[i].charcter}"
        if i < kids // 2:
            display_object.displayBuffer.append(TreeChar(kid_val, i, kids // 2 + 1))
        else:
            display_object.displayBuffer.append(TreeChar(kid_val, i + 1, kids // 2 + 1))
    return display_object


def oddKidCountTree(display_object: DisplayObject, tree: PredictionModelNode) -> DisplayObject:
    kids = tree.children_count()
    papa_position = (kids - 1) // 2
    char_val = f"{tree.charcter}"
    if tree.explict_date_fragment:
        char_val = f"{char_val}{TERMINATION_SYMBOL}"
    display_object.displayBuffer.append(TreeChar(char_val, papa_position, 0))
    display_object.height = papa_position + 2
    display_object.width = kids
    for i in range((kids - 1) // 2):
        markers = 2 * i + 3
        coeff = 1
        for j in range(markers):
            if coeff == markers // 2 + 1:
                coeff = 1
            if j < markers // 2:
                symbol = "|"
                left_pos = papa_position - coeff
                coeff += 1
                if j == markers // 2 - 1 and markers > 2:
                    symbol = "/"
                display_object.displayBuffer.append(TreeChar(symbol, left_pos, i + 1))
            elif j == markers // 2:
                display_object.displayBuffer.append(TreeChar("|", papa_position, i + 1))
            else:
                right_pos = papa_position + coeff
                coeff += 1
                symbol = "|"
                if j == markers - 1 and markers > 2:
                    symbol = "\\"
                display_object.displayBuffer.append(TreeChar(symbol, right_pos, i + 1))
    for i in range(kids):
        kid_val = f"{tree.childern[i].charcter}"
        display_object.displayBuffer.append(TreeChar(kid_val, i, kids // 2 + 1))
    return display_object


def getMaxTreeHeight(tree: PredictionModelNode) -> int:
    if tree.has_childern():
        heights = [getMaxTreeHeight(child) for child in tree.childern]
        return max(heights) + 1
    return 0


def sortTree(tree: PredictionModelNode) -> PredictionModelNode:
    if tree.has_childern():
        for idx, child in enumerate(tree.childern):
            tree.childern[idx] = sortTree(child)
        swapped = True
        if tree.children_count() <= 1:
            return tree
        while swapped:
            swapped = False
            for i in range(tree.children_count() - 1):
                this_height = getMaxTreeHeight(tree.childern[i])
                next_height = getMaxTreeHeight(tree.childern[i + 1])
                if this_height < next_height:
                    swapped = True
                    tree.childern[i], tree.childern[i + 1] = tree.childern[i + 1], tree.childern[i]
    return tree


def isFamilyUnit(tree: PredictionModelNode) -> bool:
    if tree.has_childern():
        return all(not node.has_childern() for node in tree.childern)
    return True


def getBlankLine(length: int) -> str:
    result = " "
    for _ in range(length):
        result = f" {result}"
    return result


def getRegexPattern(tree_elements: List[str]) -> str:
    tree = PredictionModelNode()
    buildTree(tree_elements, tree)
    tree = sortTree(tree)
    return _getRegexPattern(tree)


def _getRegexPattern(tree: PredictionModelNode) -> str:
    if isFamilyUnit(tree):
        return getFamilyUnitPattern(tree)
    if tree.has_childern():
        buffer = []
        buffer.append(tree.charcter)
        if tree.children_count() == 1:
            buffer.append(_getRegexPattern(tree.childern[0]))
            return "".join(buffer)
        buffer.append("(")
        for idx, kid in enumerate(tree.childern):
            buffer.append(_getRegexPattern(kid))
            if idx + 1 < tree.children_count():
                buffer.append("|")
        buffer.append(")")
        return "".join(buffer)
    return str(tree.charcter)


def getFamilyUnitPattern(tree: PredictionModelNode) -> str:
    buffer: List[str] = []
    if not tree.childern:
        return ""
    buffer.append(str(tree.charcter))
    if len(tree.childern) == 1:
        buffer.append(str(tree.childern[0].charcter))
        return "".join(buffer)
    buffer.append("([")
    for kid in tree.childern:
        buffer.append(str(kid.charcter))
    buffer.append("])")
    return "".join(buffer)


def _initialize_trees() -> None:
    monthPredictionTree.level = 0
    monthPredictionTree.charcter = "0"
    patternPredictionTree.level = 0
    patternPredictionTree.charcter = "0"
    timePredictionTree.level = 0
    timePredictionTree.charcter = "0"
    weekPredictionTree.level = 0
    weekPredictionTree.charcter = "0"

    buildTree(MONTH_FULL, monthPredictionTree)
    buildTree(MONTH_SHORT, monthPredictionTree)
    buildTree(WEEKDAY_FULL, weekPredictionTree)
    buildTree(WEEKDAY_SHORT, weekPredictionTree)
    buildTree(PATTERN, patternPredictionTree)
    buildTree(TIME_PATTERN, timePredictionTree)


_initialize_trees()
