import base64
import io
import math
import re
from functools import cache
from itertools import tee
from typing import Iterable, Iterator, NamedTuple, TypeVar

from PIL import Image, ImageDraw, ImageFont

from . import conf

T = TypeVar("T")


def pairwise(iterable: Iterable[T]) -> Iterator[tuple[T, T]]:
    """为了支持Python 3.9，补一个itertools.pairwise……"""
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)


# 虽然函数名叫truetype，但是下层调用的FreeType其实支持许多字体格式。
# 反倒是用适用于Windows的文泉驿点阵正黑渲染会有错位。
font = ImageFont.truetype("pykinezumiko/resources/wenquanyi_10pt.pcf", 13)


class Glue(NamedTuple):
    """弹性长度。

    不受迫就保持原长width，但若有需要，能拉伸到width + stretch，也能挤压到width - shrink。

    类名为“粘连”是因为TeX如此称呼。
    """

    width: float = 0.0
    stretch: float = 0.0
    shrink: float = 0.0

    def __neg__(self) -> "Glue":
        return Glue(-self[0], -self[1], -self[2])

    def __add__(self, other: "Glue") -> "Glue":
        return Glue(self[0] + other[0], self[1] + other[1], self[2] + other[2])

    def __sub__(self, other: "Glue") -> "Glue":
        return self + -other

    @property
    def stretched(self) -> float:
        return self.width + self.stretch

    @property
    def shrunk(self) -> float:
        return self.width - self.shrink

    def ratio(self, to: float) -> float:
        if to > self.width:
            try:
                return (to - self.width) / self.stretch
            except ZeroDivisionError:
                return math.inf
        elif to < self.width:
            try:
                return (to - self.width) / self.shrink
            except ZeroDivisionError:
                return -math.inf
        else:
            return 0.0

    def set(self, ratio: float = 0.0) -> float:
        if ratio >= 0.0:
            return self.width + self.stretch * ratio
        else:
            return self.width + self.shrink * ratio

    def demerit(self, to: float) -> float:
        return min(10000.0, (0.01 + abs(self.ratio(to)) ** 3) ** 2)


@cache
def measure(text: str) -> Glue:
    """计算文字的宽度。如果有字符串包含空格，会带有伸长量和压缩量。"""
    width = font.getlength(text)
    space = sum(font.getlength(match.group()) for match in re.finditer(r"\s+", text))
    stretch = space * 0.6 + text.count("\u200b") * 2.5
    return Glue(width, stretch, space * 0.2)


def is_breakable(ch: str) -> bool:
    """非常笼统的任意可断字符判断。

    在这些字符前后，只要符合行首行末禁则，即使没有空格也允许断行。
    主要包含汉字、假名、注音符号、全角符号。
    大概能一直用到Unicode 19.1版吧。
    """
    i = ord(ch)
    return (
        0x2E80 <= i < 0xA000
        or 0xF900 <= i < 0xFB00
        or 0xFF00 <= i < 0xFFF0
        or 0x20000 <= i < 0x40000
    )


def break_text(text: str, line_width: float) -> list[list[tuple[float, str]]]:
    """使文字两端对齐。

    使用简化的TeX断行算法（Knuth-Plass 1981附录A）。没有实现自动断字。

    :returns: 行构成的列表，每行由单词构成，单词用(横坐标, 字符串)表示。
    """
    if line_width <= 0.0:
        raise ValueError("line_width必须为正")
    # 在汉字前后可断行处添加零宽度空格。
    text = "".join(
        a + "\u200b"
        if (is_breakable(a) or is_breakable(b))
        and a not in " \t\n\r\f\v$([{£¥‘“〈《「『【〔〖〝﹙﹛﹝＄（［｛｢￡￥"
        and b
        not in " \t\n\r\f\v!%),.:;?]}¢°’”…‰′″›℃∶、。々〃〉》」』】〕〗〞︶︺︾﹀﹄﹚﹜﹞ぁぃぅぇぉっゃゅょゎ゛゜ゝゞァィゥェォッャュョヮヵヶ・ーヽヾ！％），．：；？］｝～｡｣､･ｧｨｩｪｫｬｭｮｯｰﾞﾟ￠"
        else a
        for a, b in pairwise(text + "?")
    )
    # 切割字符串为项目列表。
    # 项目有不可中断的单词、可断行且断行后消失的空格、段落结束。
    # 段落结束"\n"也是可断行。以其为行末，则该行成本为零。
    whitespace = r"[ \t\u2000-\u200b]"
    items: list[str] = list(filter(None, re.split(rf"(\n|{whitespace}+)", text)))
    if items and items[-1] != "\n":
        items.append("\n")
    # 优先尝试在isspace的位置断行。当在这些位置断行时，对应项目将消失。
    isspace = [item == "\n" or bool(re.match(whitespace, item)) for item in items]
    for i in range(len(items)):
        # 保留段首空格。
        if (i == 0 or items[i - 1] == "\n") and items[i] != "\n":
            isspace[i] = False
    # cumsum[i] = 前i个项目的弹性宽度和。
    cumsum = [Glue()]
    for item in items:
        i = measure(item)
        if i.shrunk > line_width:
            i = Glue(line_width - 0.5, i.stretch, i.shrink)
        cumsum.append(cumsum[-1] + i)
    # print(*zip(items, isspace, cumsum), cumsum[-1], sep="\n")
    # dp[i] = 在第i个项目处断行的(成本最小值, 达到最小值时上一个断行处的项目索引)。
    # 通常是在空格处断行。紧急情况下（例如单词超出行宽），也会在单词前断行。
    dp: list[tuple[float, int]] = [(math.inf, -1)] * len(items)
    # 首个断行点就是第一个单词。
    dp[0] = (0.0, -1)
    i = 0
    for k in range(1, len(items)):
        if isspace[k]:
            while (cumsum[k] - cumsum[i + isspace[i]]).shrunk > line_width:
                i += 1
            dp[k] = min(
                (
                    dp[j][0]
                    + (
                        0.0
                        if items[k] == "\n"
                        else (cumsum[k] - cumsum[j + isspace[j]]).demerit(line_width)
                    ),
                    j,
                )
                for j in range(i, k)
                if math.isfinite(dp[j][0])
            )
            # 强制在段落结束处断行。
            if items[k] == "\n":
                i = k
    # 追踪断行项目索引。
    breaks: list[int] = []
    i = len(items) - 1
    while i >= 0:
        breaks.append(i)
        i = dp[i][1]
    breaks.reverse()
    # 整理用于绘制的(坐标, 单词)列表。
    lines: list[list[tuple[float, str]]] = []
    for i, k in pairwise(breaks):
        i += isspace[i]
        ratio = 0.0 if items[k] == "\n" else (cumsum[k] - cumsum[i]).ratio(line_width)
        if math.isinf(ratio):
            ratio = 0.0
        lines.append(
            [
                ((cumsum[j] - cumsum[i]).set(ratio), items[j])
                for j in range(i, k)
                if not isspace[j]
            ]
        )
    return lines


def text_bitmap(
    text="string\nlorem ipsum 114514\n1919810\n共计处理了489975条消息",
    font=font,
    width=274,
    line_height=28,
    margin=8,
    border=3,
    padding_inline=12,
    padding_block=4,
    scale=2,
    dash_on=4,
    dash_off=4,
):
    lines = break_text(text, width)
    height = line_height * len(lines) - 1
    img = Image.new(
        "RGB",
        (
            width + (margin + border + padding_inline) * 2,
            height + (margin + border + padding_block) * 2,
        ),
        conf.THEME[3],
    )
    draw = ImageDraw.Draw(img)
    draw.rectangle(
        ((0, 0), img.size),
        outline=conf.THEME[2],
        width=margin,
    )
    draw.rectangle(
        ((margin, margin), (img.width - margin, img.height - margin)),
        outline=conf.THEME[1],
        width=border,
    )
    for y in range(line_height - 1, height, line_height):
        y += margin + border + padding_block
        for x in range(0, width, dash_on + dash_off):
            x += margin + border + padding_inline
            img.paste(conf.THEME[2], (x, y, x + dash_on, y + 1))
    for y, line in enumerate(lines):
        y *= line_height
        y += margin + border + padding_block + font.size // 2
        for x, item in line:
            x += margin + border + padding_inline
            draw.text((x, y), item, fill=conf.THEME[0], font=font)
    return img.resize((img.width * scale, img.height * scale), resample=Image.BOX)


def pil_image_to_base64(img: Image.Image) -> str:
    with io.BytesIO() as f:
        img.save(f, format="PNG")
        return base64.b64encode(f.getvalue()).decode()
