import os.path
import unicodedata
from bisect import bisect_right
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


def normalize(text: str) -> str:
    r"""激进地统一字符串为规范形式。

    将对输入字符串" Ｆｏｏ  BÄR\x00114514 \r\n"进行下述Unicode变换。

    - 删除不应出现在人类产生的文本中的字符。
        → " Ｆｏｏ  BÄR114514 \n"
    - 消去开头和结尾的空白符。
        → "Ｆｏｏ  BÄR114514"
    - 标准分解（NFD）。拆分出独立的重音符号。
        → "Ｆｏｏ  BA\u0308R114514"
    - case folding。简单地说就是变成小写。一些语言有额外变换（ß → ss，ς → σ等）。
        → "ｆｏｏ  ba\u0308r114514"
    - 兼容分解形式标准化（NFKD）。简单地说就是把怪字转换为正常字，比如全角变成半角。
        → "foo  ba\u0308r114514"
    - case folding。
    - 兼容分解形式标准化（NFKD）。套两层是因为㎯这样的方块字母。参照Unicode标准之默认大小写算法。
        A string X is a compatibility caseless match for a string Y if and only if:
            NFKD(toCasefold(NFKD(toCasefold(NFD(X))))) =
                NFKD(toCasefold(NFKD(toCasefold(NFD(Y)))))
    - 删去组合字符。一些语言的语义可能受到影响（é → e，が → か等）。
        → "foo  bar114514"
    - 替换连续的空白符和下划线为单个下划线。
        → "foo_bar114514"
    """
    text = scrub(text)
    text = text.strip()
    text = unicodedata.normalize("NFD", text)
    text = text.casefold()
    text = unicodedata.normalize("NFKD", text)
    text = text.casefold()
    text = unicodedata.normalize("NFKD", text)
    text = regex.sub(r"\p{M}+", "", text)
    text = regex.sub(r"[\s_]+", "_", text)
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
    index = bisect_right(range(len(text) + 1), command_name, key=lambda i: normalize(text[:i])) - 1
    assert index >= 0, "析出长度为负的命令名。"
    if normalize(text[:index]) != command_name:
        # 命令名与参数的边界落在字符之内，无法不多不少地切下命令名。复合字母可能引起此问题。
        return None
    return command_name, text[index:].rstrip()


class CommandSyntaxError(Exception):
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


class UIException(Exception):
    pass
