import re
import typing
import unicodedata
from itertools import filterfalse, groupby
from typing import Any, NoReturn, Never, SupportsInt, Union
from types import UnionType


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


def to_number(s: str) -> int | float:
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
    return re.sub(
        r"[\s_]+",
        "_",
        "".join(
            filterfalse(
                unicodedata.combining,
                unicodedata.normalize(
                    "NFKD",
                    unicodedata.normalize(
                        "NFKD",
                        unicodedata.normalize("NFD", text.strip()).casefold(),
                    ).casefold(),
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


def match_start_or_end(pattern: str, text: str, flags=0) -> re.Match[str] | None:
    return re.match(pattern, text, flags) or re.search(rf"(?:{pattern})\Z", text, flags)


def parse_command(
    parameters: dict[str, tuple[type, bool]],
    given_arguments: dict[str, Any],
    text: str,
) -> dict[str, Any]:
    """根据需要的参数类型从命令名之后的字符串中宽容地解析参数。

    :param parameters: 需要的参数名到(参数类型, 是否可选)的映射。将按字典顺序依次提取参数。

    仅支持下列基本数据类型。

    - Never（NoReturn）。该参数必定匹配失败。因为匹配失败时会显示帮助信息，所以可用于实现.help等没有实际功能的命令。
    - int和float。
    - str。因为参数用空白分割，只有最后一个str参数才会笼络空白。
    - Union。易碎的细节：按指定顺序匹配，因此int | str可能传入整数或字符串，而str | int等同于str。
    - Optional。

    :param given_arguments: 已知的参数。如果需要其中的参数，就直接赋予，不从字符串中解析。
    :param text: 待解析的字符串。
    :raises: CommandSyntaxError
    """
    kwargs = {}
    first_parameter = True
    last_str_parameter_name = None
    for name, (parameter, optional) in parameters.items():
        if name in given_arguments:
            kwargs[name] = given_arguments[name]
            continue

        # 在匹配每个参数之前，先去除字符串两端的空白。
        text = text.strip()

        # 根据参数类型匹配字符串。
        for parameter in (
            typing.get_args(parameter)
            if typing.get_origin(parameter) in (Union, UnionType)
            else (parameter,)
        ):
            # NoReturn is not Never，什么鬼？
            if parameter is NoReturn or parameter is Never:
                match = None
            elif parameter is None or parameter is type(None):
                # 以Optional[int]（= Union[int, None]）为例。
                # 遇到None时表明当前处在Optional中，而int无法匹配。
                # 此时在参数项中放入None，将参数视为有默认值，不阻止后续类型匹配成功覆盖此参数值。
                match = None
                kwargs[name] = None
                optional = True
            elif parameter is int:
                match = match_start_or_end(
                    r"[+-]?(\d+|0x[0-9a-f]+|0o[0-7]+|0b[01]+)", text, re.IGNORECASE
                )
            elif parameter is float:
                match = match_start_or_end(
                    r"[+-]?(\d*\.\d*|0x[0-9a-f]*\.[0-9a-f]*p\d+|\d+)",
                    text,
                    re.IGNORECASE,
                )
            elif parameter is str:
                last_str_parameter_name = name
                match = re.match(r"\S+", text)
            else:
                raise CommandSyntaxError(f"插件命令的参数 {name} 拥有不能理解的参数类型 {parameter}。")
            # 将值填入参数表中。
            if match:
                first_parameter = False
                kwargs[name] = parameter(match.group())
                text = text[: match.start()] + text[match.end() :]
                break
        else:
            if optional:
                pass
            elif first_parameter:
                raise CommandSyntaxError()
            else:
                raise CommandSyntaxError(f"解析命令时找不到参数 {name}。")

    # 清理解析完所有参数后剩下的字符串。
    if text.lstrip():
        if last_str_parameter_name:
            kwargs[last_str_parameter_name] += text
        else:
            raise CommandSyntaxError(f"残留未成功解析的参数“{text}”。")
    return kwargs


class CommandSyntaxError(Exception):
    pass
