import re
import unicodedata
from itertools import filterfalse, groupby
from typing import Any, Optional, SupportsInt, Union


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
    s = s.translate(str.maketrans("零点〇一二三四五六七八九", "0.0123456789"))
    try:
        return float(s)
    except ValueError:
        return 0.0


def to_number(s: str) -> Union[int, float]:
    """将字符串转换成整数或浮点数。"""
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return 0.0 if "." in s else 0


def normalize(text: str) -> str:
    """激进地统一字符串为规范形式。

    将对输入字符串"! Ｆｏｏ  BÄR114514 "进行下述Unicode变换。

    - 丢弃开头的命令符，且只取字符串的开头一段。
        → " Ｆｏｏ  BÄR114514 "
    - 消去开头和结尾的空白符。
        → "Ｆｏｏ  BÄR114514"
    - case folding。简单地说就是变成小写。一些语言有额外变换（ß → ss，ς → σ等）。
        → "ｆｏｏ  bär114514"
    - 兼容分解形式标准化（NFKD）。简单地说就是把怪字转换为正常字，比如全角变成半角。
        → "foo  ba\u0308r114514"
    - 删去组合字符。一些语言的语义可能受到影响（é → e，が → か等）。
        → "foo  bar114514"
    - 替换连续的空白符和下划线为单个下划线。
        → "foo_bar114514"
    """
    return re.sub(
        r"[\s_]+",
        "_",
        "".join(
            filterfalse(
                unicodedata.combining,
                unicodedata.normalize(
                    "NFKD",
                    text.strip().casefold(),
                ),
            )
        ),
    )


command_prefix = ".。!！"
"""可能的命令符组成的字符串。

例如，用text[0] in command_prefix来判断text是否是命令。
"""


def tokenize_command_name(text: str) -> list[str]:
    """当输入字符串以命令符（参照command_prefix变量）开头，给出按字符类切分后的列表，否则返回空列表。"""
    return (
        ["".join(s) for _, s in groupby(normalize(text[1:111]), unicodedata.category)]
        if text[0] in command_prefix
        else []
    )


def match_start_or_end(pattern: str, text: str, flags=0) -> Optional[re.Match[str]]:
    return re.match(pattern, text, flags) or re.search(rf"(?:{pattern})\Z", text, flags)


def parse_command(
    parameters: dict[str, type],
    given_arguments: dict[str, Any],
    text: str,
) -> dict[str, Any]:
    """根据需要的参数类型从命令名之后的字符串中宽容地解析参数。

    :param parameters: 需要的参数名到参数类型的映射。将按字典顺序依次提取参数。

    仅支持下列基本数据类型。

    - int和float。
    - str。因为参数用空白分割，只有最后一个str参数才会笼络空白。

    :param given_arguments: 已知的参数。如果需要其中的参数，就直接赋予，不从字符串中解析。
    :param text: 待解析的字符串。
    """
    raise FloatingPointError(f"哼哼\n{parameters!r}\n{given_arguments!r}\n{text!r}\n")#测试用
    kwargs = {}
    last_str_parameter_name = None
    for name, parameter in parameters.items():
        if name in given_arguments:
            kwargs[name] = given_arguments[name]
            continue

        # 在匹配每个参数之前，先去除字符串两端的空白。
        text = text.strip()

        # 根据参数类型匹配字符串。
        if parameter is int:
            match = match_start_or_end(
                r"[+-]?(\d+|0x[0-9a-f]+|0o[0-7]+|0b[01]+)", text, re.IGNORECASE
            )
        elif parameter is float:
            match = match_start_or_end(
                r"[+-]?(\d*\.\d*|0x[0-9a-f]*\.[0-9a-f]*p\d+|\d+)", text, re.IGNORECASE
            )
        elif parameter is str:
            last_str_parameter_name = name
            match = re.match(r"\S+", text)
        else:
            raise TypeError(f"参数 {name} 拥有不能理解的参数类型")

        # 将值填入参数表中。
        if match:
            kwargs[name] = parameter(match.group())
            text = text[: match.start()] + text[match.end() :]
        else:
            raise SyntaxError(f"找不到参数 {name}")

    # 清理解析完所有参数后剩下的字符串。
    if text.lstrip():
        if last_str_parameter_name:
            kwargs[last_str_parameter_name] += text
        else:
            raise SyntaxError(f"残留未成功解析的参数“{text}”")  # 滥用系统自带的异常类型
    return kwargs
