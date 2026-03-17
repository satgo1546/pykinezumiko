import math
import os.path
import unicodedata
from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from typing import SupportsInt

import regex


def format_timespan(seconds: SupportsInt) -> str:
    r = []
    seconds = int(seconds)
    if seconds >= 86400:
        r.append(str(seconds // 86400))
        r.append("天")
    seconds %= 86400
    if seconds >= 3600:
        r.append(str(seconds // 3600))
        r.append("小时")
    seconds %= 3600
    if seconds >= 60:
        r.append(str(seconds // 60))
        r.append("分")
    seconds %= 60
    r.append(str(seconds))
    r.append("秒")
    return " ".join(r)


def parse_number(s: str, default=0) -> float:
    """将可能含有汉字的字符串转换成对应的数值。"""
    s = s.strip()
    if not s:
        return default
    try:
        return float(s)
    except ValueError:
        pass
    for c, v in (
        ("亿", 100000000),
        ("億", 100000000),
        ("万", 10000),
        ("千", 1000),
        ("百", 100),
        ("十", 10),
    ):
        head, c, tail = s.partition(c)
        if c:
            return parse_number(head, 1) * v + parse_number(tail)
    s = s.translate(str.maketrans("〇一二三四五六七八九点零壹贰叁肆伍陆柒捌玖", "0123456789.0123456789"))
    try:
        return float(s)
    except ValueError:
        return 0.0


def to_number(s: str) -> int | float:
    """将字符串转换成整数或浮点数。"""
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return 0.0 if "." in s else 0


def scrub(text: str) -> str:
    r"""删除不应出现在人类产生的文本中的字符。

    会删除除了换行符（"\n"）和制表符（"\t"）以外的所有控制字符、孤代理对、非字符。

    因为会删除"\a"，返回的字符串可安全地作为纯文本而不会包含木鼠子码控制序列。
    但是，返回值可能包含"< >"等字符，因此不能直接作为木鼠子码控制序列参数使用。
    """
    return regex.sub(r"[\p{Cc}\p{Cs}\p{Noncharacter_Code_Point}--\t\n]+", "", text, flags=regex.VERSION1)


def ellipsize(text: str, length: int) -> str:
    """在过长的字符串结尾添加省略号，使结果的length属性不超过给定的length参数。

    函数名来自[Android TextView](https://developer.android.com/reference/android/widget/TextView#attr_android:ellipsize)。
    """

    if length <= 0:
        return ""
    if length >= len(text):
        return text
    # 要是regex支持\b{g}就好了！
    # https://unicode.org/reports/tr18/#RL2.2
    for match in regex.finditer(r"\X", text, pos=max(0, length - 128)):
        if match.end() >= length:
            return text[: match.start()] + "…"
    assert False


def short(text: str, length: int) -> str:
    """截去过长的字符串的中间部分，使结果的len()不超过给定的length参数。结果未必最优。

    函数名和截断留下的骨架样式来自[Wolfram语言](https://reference.wolfram.com/language/ref/Short.html)。
    """
    if length < 16:
        raise ValueError("长度限制太短")
    if length >= len(text):
        return text
    h = (length - (len(str(len(text))) + 4)) >> 1
    assert h > 0
    for match in regex.finditer(r"\X", text, pos=max(0, length - 128)):
        if match.end() > h:
            i = match.start()
            break
    else:
        assert False
    match = regex.match(r"\X", text, pos=len(text) - h - 1)
    assert match
    j = match.end()
    return f"{text[:i]} ≪{j - i}≫ {text[j:]}"


def normalize(text: str) -> str:
    r"""激进地统一字符串为规范形式。

    将对输入字符串" Ｆｏｏ  BÄR\x00114514 \r\n"进行下述Unicode变换。

    - 删除不应出现在人类产生的文本中的字符。
        → " Ｆｏｏ  BÄR114514 \n"
    - 标准分解（NFD）。拆分出独立的重音符号。
        → " Ｆｏｏ  BA\u0308R114514 \n"
    - case folding。简单地说就是变成小写。一些语言有额外变换（ß → ss，ς → σ等）。
        → " ｆｏｏ  ba\u0308r114514 \n"
    - 兼容分解形式标准化（NFKD）。简单地说就是把怪字转换为正常字，比如全角变成半角。
        → " foo  ba\u0308r114514 \n"
    - case folding。
    - 兼容分解形式标准化（NFKD）。套两层是因为㎯这样的方块字母。参照Unicode标准之默认大小写算法。
        A string X is a compatibility caseless match for a string Y if and only if:
            NFKD(toCasefold(NFKD(toCasefold(NFD(X))))) =
                NFKD(toCasefold(NFKD(toCasefold(NFD(Y)))))
    - 删去组合字符、修饰字符、部分标点符号、空白。一些语言的语义可能受到影响（é → e，が → か等）。
        → "foobar114514"
    """
    text = scrub(text)
    text = unicodedata.normalize("NFD", text)
    text = text.casefold()
    text = unicodedata.normalize("NFKD", text)
    text = text.casefold()
    text = unicodedata.normalize("NFKD", text)
    text = regex.sub(r"[\p{M}\p{Sk}\p{Pc}\p{Pd}\p{Po}\s]+", "", text)
    return text


def parse_command(text: str, sorted_normalized_command_names: Sequence[str]) -> tuple[str, str] | None:
    """当输入字符串以命令符开头且其后紧随某个命令名时，给出命令名和其余文本，否则返回None。"""
    match = regex.match(r"[.。!！]", text)
    if not match:
        return None
    text = text[match.end() :]
    command = normalize(text)
    index = bisect_right(sorted_normalized_command_names, command) - 1
    if index < 0:
        return None
    command_name = sorted_normalized_command_names[index]
    if not command.startswith(command_name):
        return None
    # 在原始字符串中二分找到命令名之后的部分。
    index = bisect_left(range(len(text)), command_name, key=lambda i: normalize(text[:i]))
    if index:
        # 保证切点在字符边界（不会把单个字符切成两半）。
        grapheme = regex.match(r"\X", text, pos=index - 1)
        assert grapheme, f"{text!r}[{index - 1}] 处找不到字符？！"
        index = grapheme.end()
    if normalize(text[:index]) != command_name:
        # 命令名与参数的边界落在字符之内，无法不多不少地切下命令名。复合字母可能引起此问题。
        return None
    return command_name, text[index:].rstrip()


class CommandSyntaxError(Exception):
    pass


class UIException(Exception):
    pass


def format_exception(e: Exception) -> str:
    tb = e.__traceback__
    if tb:
        while tb.tb_next:
            tb = tb.tb_next
        tb = tb.tb_frame
        source = f"{os.path.basename(tb.f_code.co_filename)}:{tb.f_lineno}:{tb.f_code.co_name}"
    else:
        source = "???"
    return f"来自 {source} 的 {type(e).__name__}：{e}"


_FORMAT_OBJECT_STR_TRANSLATE = (
    {i: chr(0x2400 + i) for i in range(0x20)} | {0x7F: "\u2421"} | {i: f"\\x{i:02X}" for i in range(0x80, 0xA0)}
)


def format_object(obj: object) -> str:
    """输出任意无环对象为紧凑的类JSON格式。

    主要用于输出JSON payload到消息。输出仅供人类阅读，无法被反序列化。
    """
    match obj:
        case None:
            return "∅"
        case True:
            return "✓"
        case False:
            return "✗"
        case int(_):
            return str(obj)
        case float(_):
            if math.isnan(obj):
                return "NaN"
            if math.isinf(obj):
                return "-∞" if obj < 0 else "∞"
            return str(obj).replace("+0", "+").replace("-0", "-").replace("e+", "e")
        case complex(real=real, imag=imag):
            real = "" if real == 0.0 else format_object(real)
            imag = format_object(imag)
            if not imag.startswith("-"):
                imag = "+" + imag
            return (real + imag + "i").replace(".0", "")
        case str(_):
            return "'" + obj.translate(_FORMAT_OBJECT_STR_TRANSLATE) + "'"
        case bytes(_):
            return "b'" + obj.decode("iso-8859-1").translate(_FORMAT_OBJECT_STR_TRANSLATE) + "'"
        case bytearray(_):
            return "b[" + obj.decode("iso-8859-1").translate(_FORMAT_OBJECT_STR_TRANSLATE) + "]"
        case tuple(_):
            return "(" + ", ".join(map(format_object, obj)) + ")"
        case list(_):
            if not obj:
                return "[]"
            if all(isinstance(x, (int, float, complex)) for x in obj):
                return "[" + " ".join(map(format_object, obj)) + "]"
            if all(isinstance(x, str) for x in obj):
                return "[" + ", ".join(obj) + "]"
            return "[" + ", ".join(map(format_object, obj)) + "]"
        case dict(_):
            s = ""
            for k, v in obj.items():
                s += k if isinstance(k, str) else format_object(k)
                s += "∅" if v is None else f": {format_object(v)}"
                s += ", "
            return "{" + s[:-2] + "}"
        case set(_) | frozenset(_):
            return "{" + ", ".join(map(format_object, obj)) + "}"
        case _:
            return repr(obj)
