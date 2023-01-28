"""Microsoft Excel 2007 XLSX文件读写库。

基于pydpiper开发的pylightxl改写。
pylightxl是轻量级、零依赖的Excel电子表格数据、公式、批注读写库，支持Python 2.7.18+。
该库的代码仅一个文件，有完整的类型标注，可惜不知为何没能进到awesome-python列表中。
https://github.com/PydPiper/pylightxl
https://pylightxl.readthedocs.io/

不支持读写公式、批注、主题。
不压缩写出的工作簿。在今日硬件上，不压缩的性能往往更好。
这还有助于全体打包时使用更高压缩率的算法，而非受限于ZIP通行的DEFLATE。

【动机】
openpyxl即使在只读与只写模式下也慢得很。
pylightxl在创建xl/sharedStrings.xml时采用了线性查找而非散列表。
不知性能问题是否与库默认的ZIP压缩选项有关。
因为需要一种快速写入的方法，自己编写了库。
"""

import datetime
import html
import math
import os
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping
from functools import reduce
from itertools import groupby
from typing import IO, Any, Callable, Literal, Optional, Union

CellPrimitive = Union[None, bool, int, float, str]
"""单元格值的类型。

无法区分整数和浮点数，NaN和无穷也无法准确存储。
"""

CellValue = Union[CellPrimitive, datetime.datetime, bytes]
"""通过单元格数值格式，额外支持的单元格值类型。"""

Color = Union[tuple[int, int, int], tuple[int, int, int, int], str]
"""RGB元组，RGBA元组，或#RRGGBB、#RRGGBBAA格式的字符串。"""


def color_to_hex(color: Color) -> str:
    """转换Color类型数据到十六进制ARGB字符串。"""
    if isinstance(color, tuple):
        if len(color) == 3:
            return "ff%02x%02x%02x" % color
        else:
            return "%02x%02x%02x%02x" % (color[3:] + color[:3])
    else:
        color = color.removeprefix("#")
        if len(color) == 6:
            return "ff" + color
        else:
            return color[6:] + color[:6]


CellBorderStyle = Literal[
    "none",
    "thin",
    "medium",
    "dashed",
    "dotted",
    "thick",
    "double",
    "hair",
    "mediumDashed",
    "dashDot",
    "mediumDashDot",
    "dashDotDot",
    "mediumDashDotDot",
    "slantDashDot",
]


class CellStyle:
    """单元格格式。"""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.number_format: str = "General"

        self.font_name: str = "Courier New"
        self.font_size: float = 10.0
        self.bold: bool = False
        self.italic: bool = False
        self.underline: bool = False
        self.strikethrough: bool = False
        self.subscript: bool = False
        self.superscript: bool = False
        self.color: Color = (0, 0, 0)

        self.fill: Color = (255, 255, 255)

        self.border_style = "none"
        self.border_color = (0, 0, 0)
        self.border_diagonal_down: bool = False
        self.border_diagonal_up: bool = False

        self.width: float = 8
        self.height: float = 16
        """列宽和行高。
        
        并不是单元格的格式，而是整行和整列的格式，在单个单元格上设置宽度和高度无效。
        但是因为styler函数中第−1列表示整行，第−1行表示整列，将尺寸信息写在这里非常方便。
        """

    # 我去，匿名装饰器！
    # 该装饰器创建一个只可写入的属性。
    @lambda f: property(fset=f)
    def border_style(self, style: CellBorderStyle):
        self.border_top_style: CellBorderStyle = style
        self.border_right_style: CellBorderStyle = style
        self.border_bottom_style: CellBorderStyle = style
        self.border_left_style: CellBorderStyle = style
        self.border_diagonal_style: CellBorderStyle = style

    @lambda f: property(fset=f)
    def border_color(self, color: Color):
        self.border_top_color: Color = color
        self.border_right_color: Color = color
        self.border_bottom_color: Color = color
        self.border_left_color: Color = color
        self.border_diagonal_color: Color = color

    def font_spec(self) -> str:
        return (
            f'<font><name val="{html.escape(self.font_name)}"/><sz val="{self.font_size}"/>'
            + ("<b/>" if self.bold else "")
            + ("<i/>" if self.italic else "")
            + ("<u/>" if self.underline else "")
            + ("<strike/>" if self.strikethrough else "")
            + (
                '<vertAlign val="subscript"/>'
                if self.subscript
                else '<vertAlign val="superscript"/>'
                if self.superscript
                else ""
            )
            + f'<color rgb="{color_to_hex(self.color)}"/></font>'
        )

    def fill_spec(self) -> str:
        return f'<fill><patternFill patternType="solid"><fgColor rgb="{color_to_hex(self.fill)}"/></patternFill></fill>'

    def border_spec(self) -> str:
        return (
            "<border"
            + (' diagonalUp="1"' if self.border_diagonal_up else "")
            + (' diagonalDown="1"' if self.border_diagonal_down else "")
            + f""">
<left style="{self.border_left_style}">
<color rgb="{color_to_hex(self.border_left_color)}"/></left>
<right style="{self.border_right_style}">
<color rgb="{color_to_hex(self.border_right_color)}"/></right>
<top style="{self.border_top_style}">
<color rgb="{color_to_hex(self.border_top_color)}"/></top>
<bottom style="{self.border_bottom_style}">
<color rgb="{color_to_hex(self.border_bottom_color)}"/></bottom>
<diagonal style="{self.border_diagonal_style}">
<color rgb="{color_to_hex(self.border_diagonal_color)}"/></diagonal>
</border>"""
        )


NUMBER_FORMATS = {
    0: "General",
    1: "0",
    2: "0.00",
    3: "#,##0",
    4: "#,##0.00",
    5: '"$"#,##0_);("$"#,##0)',
    6: '"$"#,##0_);[Red]("$"#,##0)',
    7: '"$"#,##0.00_);("$"#,##0.00)',
    8: '"$"#,##0.00_);[Red]("$"#,##0.00)',
    9: "0%",
    10: "0.00%",
    11: "0.00E+00",
    12: "# ?/?",
    13: "# ??/??",
    14: "mm-dd-yy",
    15: "d-mmm-yy",
    16: "d-mmm",
    17: "mmm-yy",
    18: "h:mm AM/PM",
    19: "h:mm:ss AM/PM",
    20: "h:mm",
    21: "h:mm:ss",
    22: "m/d/yy h:mm",
    # 27..36和50..58在不同语言中有不同的定义，甚至类型都不一样。
    # 只使用用户级的格式代码并不能做到自适应。
    27: '[$-404]e/m/d;yyyy"年"m"月";[$-411]ge.m.d;yyyy"年" mm"月" dd"日"',
    28: '[$-404]e"年"m"月"d"日";m"月"d"日";[$-411]ggge"年"m"月"d"日";mm-dd',
    29: '[$-404]e"年"m"月"d"日";m"月"d"日";[$-411]ggge"年"m"月"d"日";mm-dd',
    30: "m/d/yy;m-d-yy;m/d/yy;mm-dd-yy",
    31: 'yyyy"年"m"月"d"日";yyyy"年"m"月"d"日";yyyy"年"m"月"d"日";yyyy"년" mm"월" dd"일"',
    32: 'hh"時"mm"分";h"时"mm"分";h"時"mm"分";h"시" mm"분"',
    33: 'hh"時"mm"分"ss"秒";h"时"mm"分"ss"秒";h"時"mm"分"ss"秒";h"시" mm"분" ss"초"',
    34: '上午/下午hh"時"mm"分";上午/下午h"时"mm"分";yyyy"年"m"月";yyyy-mm-dd',
    35: '上午/下午hh"時"mm"分"ss"秒";上午/下午h"时"mm"分"ss"秒";m"月"d"日";yyyy-mm-dd',
    36: '[$-404]e/m/d;yyyy"年"m"月";[$-411]ge.m.d;yyyy"年" mm"月" dd"日"',
    37: "#,##0_);(#,##0)",
    38: "#,##0_);[Red](#,##0)",
    39: "#,##0.00_);(#,##0.00)",
    40: "#,##0.00_);[Red](#,##0.00)",
    41: r'_(* #,##0_);_(* \(#,##0\);_(* "-"_);_(@_)',
    42: r'_("$"* #,##0_);_("$"* \(#,##0\);_("$"* "-"_);_(@_)',
    43: r'_(* #,##0.00_);_(* \(#,##0.00\);_(* "-"??_);_(@_)',
    44: r'_("$"* #,##0.00_)_("$"* \(#,##0.00\)_("$"* "-"??_)_(@_)',
    45: "mm:ss",
    46: "[h]:mm:ss",
    47: "mmss.0",
    48: "##0.0E+0",
    49: "@",
    50: '[$-404]e/m/d;yyyy"年"m"月";[$-411]ge.m.d;yyyy"年" mm"月" dd"日"',
    51: '[$-404]e"年"m"月"d"日";m"月"d"日";[$-411]ggge"年"m"月"d"日";mm-dd',
    52: '上午/下午hh"時"mm"分";yyyy"年"m"月";yyyy"年"m"月";yyyy-mm-dd',
    53: '上午/下午hh"時"mm"分"ss"秒";m"月"d"日";m"月"d"日";yyyy-mm-dd',
    54: '[$-404]e"年"m"月"d"日";m"月"d"日";[$-411]ggge"年"m"月"d"日";mm-dd',
    55: '上午/下午hh"時"mm"分";上午/下午h"时"mm"分";yyyy"年"m"月";yyyy-mm-dd',
    56: '上午/下午hh"時"mm"分"ss"秒";上午/下午h"时"mm"分"ss"秒";m"月"d"日";yyyy-mm-dd',
    57: '[$-404]e/m/d;yyyy"年"m"月";[$-411]ge.m.d;yyyy"年" mm"月" dd"日"',
    58: '[$-404]e"年"m"月"d"日";m"月"d"日";[$-411]ggge"年"m"月"d"日";mm-dd',
    59: "t0",
    60: "t0.00",
    61: "t#,##0",
    62: "t#,##0.00",
    67: "t0%",
    68: "t0.00%",
    69: "t# ?/?",
    70: "t# ??/??",
    71: "ว/ด/ปปปป",
    72: "ว-ดดด-ปป",
    73: "ว-ดดด",
    74: "ดดด-ปป",
    75: "ช:นน",
    76: "ช:นน:ทท",
    77: "ว/ด/ปปปป ช:นน",
    78: "นน:ทท",
    79: "[ช]:นน:ทท",
    80: "นน:ทท.0",
    81: "d/m/bb",
}

EPOCH = datetime.datetime(1899, 12, 30)
"""Excel元年。

Excel没有专门的日期/时间类型，而是用数字代替，就像Unix时间戳一样。
单元格内存储的数值表示从1900年1月0日起、包含1900年2月29日在内的天数（？？？）。
而且，作为深度本地化的受害者，是按计算机设置的时区计算的。

- 0.5 = 当地时间1900年1月0日12:00:00，Excel无法显示1899年及以前的日期
- π = 当地时间1900年1月3日03:23:53.605
- 7162+42314/86400 = 当地时间1919年8月10日11:45:14
- 25569 = 当地时间1970年1月1日00:00:00

然而，因为早期Macintosh电脑不支持1904年以前的日期，所以改成了1904年1月0日起的天数。
直到今天，仍然可以在工作簿选项中自选“使用1904日期系统”。大混乱。
为了不被迫感受小小的Excel震撼，建议不要在数据交换中使用Excel的日期与时间。

https://learn.microsoft.com/en-us/office/troubleshoot/excel/wrongly-assumes-1900-is-leap-year
https://learn.microsoft.com/en-us/office/troubleshoot/excel/1900-and-1904-date-system
"""


def column_letter_to_number(s: str) -> int:
    """转换字母列名到从0开始的列编号。

    - "A" → 0
    - "AAA" → 702
    """
    # 注意编号起始值与下题不同！
    # https://leetcode.com/problems/excel-sheet-column-number/
    if len(s) > 7 or not s.isascii() or not s.isupper():
        raise ValueError("错误的列名：应为一个或多个大写字母")
    return reduce(lambda s, c: s * 26 + ord(c) - 64, s, 0) - 1


def column_number_to_letter(n: int) -> str:
    """转换从0开始的列编号到字母列名。

    - 0 → "A"
    - 702 → "AAA"
    """
    # 注意编号起始值与下题不同！
    # https://leetcode.com/problems/excel-sheet-column-title/
    s = ""
    while n >= 0:
        s = chr(n % 26 + 65) + s
        n = n // 26 - 1
    return s


def parse_cell_reference(address: str) -> tuple[int, int]:
    """转换A1和R1C1这样对单个单元格的引用到从0开始的行列索引。

    即使在Excel选项中选择了R1C1格式，存储的文件中也仍然采用A1格式，单元格也好，公式也是。
    天哪，这居然是个正确的决定！那为什么各种名称要存储成本地化的字符串？
    """
    if match := re.fullmatch(r"([A-Z]+)([0-9]+)", address.upper()):
        return int(match.group(2)) - 1, column_letter_to_number(match.group(1))
    elif match := re.fullmatch(r"R(\d+)C(\d+)", address, re.ASCII | re.IGNORECASE):
        return int(match.group(1)) - 1, int(match.group(2)) - 1
    else:
        raise ValueError("错误的单元格引用格式：应类似A1或R1C1")


def pool(index_base: int = 0) -> defaultdict[Any, int]:
    """创建一个值池，即从值到加入顺序（从指定索引开始）的映射。

    值是新的时，产生新的索引，否则返回原有索引。用于共享字符串池、样式表索引的生成。

        x = pool(100)
        assert x["foo"] == 100
        assert x["bar"] == 101
        assert x["baz"] == 102
        assert x["bar"] == 101
        assert x["foobar"] == 103
    """
    x = defaultdict(lambda: len(x) + index_base)
    return x


def read(
    file: Union[str, os.PathLike[str], IO[bytes]]
) -> dict[str, defaultdict[tuple[int, int], CellValue]]:
    """读取指定的工作簿。

    返回对象可以以下列形式使用：

        workbook = read("input.xlsx")
        worksheet = workbook["Sheet1"]
        cell = worksheet[8, 4]  # 第8行第4列，下标从0开始
        print("Sheet1!E9的值是", cell)

    由Excel文件格式保证工作表字典键已排序。
    """
    with zipfile.ZipFile(file, "r") as z:
        # 先定义一个方便函数。
        def xq(filename: str, xpath: str) -> Iterator[ET.Element]:
            """从已打开的这个压缩包中解析XML文件、直达要害节点。"""
            with z.open(filename, "r") as f:
                return ET.parse(f).getroot().iterfind(xpath)

        # 从工作簿关系文件中提取从rId×××到sheet×××.xml的映射。
        workbook_rels = {
            # Microsoft Excel写出的是相对路径，但openpyxl会写出相对于压缩包根的绝对路径……
            # ZipFile需要的是相对于压缩包根的相对路径。
            el.get("Id", ""): "xl/" + el.get("Target", "").removeprefix("/xl/")
            for el in xq("xl/_rels/workbook.xml.rels", "./{*}Relationship")
        }

        # 从工作簿清单中按顺序枚举工作表，根据记录的关系，产生从工作表名到工作表XML文件路径的映射。
        sheets = {
            el.get("name", ""): workbook_rels[
                el.get(
                    # openpyxl有时候不输出"r"命名空间……
                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id",
                    el.get("id", ""),
                )
            ]
            for el in xq("xl/workbook.xml", "./{*}sheets/{*}sheet")
        }

        # 取出共享字符串池为字符串列表。共享字符串池的下标从0开始。
        if "xl/sharedStrings.xml" in z.NameToInfo:
            shared_strings = [
                "".join(t.text or "" for t in el.iterfind(".//{*}t"))
                for el in xq("xl/sharedStrings.xml", "./{*}si")
            ]
        else:
            shared_strings = []

        # 取出工作簿的样式表。
        if "xl/styles.xml" in z.NameToInfo:
            number_formats = NUMBER_FORMATS | {
                int(el.get("numFmtId", "-1")): el.get("formatCode", "")
                for el in xq("xl/styles.xml", "./{*}numFmts/{*}numFmt")
            }
            style_number_formats = [
                number_formats.get(int(el.get("numFmtId", "")), "General")
                for el in xq("xl/styles.xml", "./{*}cellXfs/{*}xf")
                if el.get("numFmtId")
            ] or ["General"]
        else:
            style_number_formats = ["General"]

        # 读取工作表数据。
        workbook: dict[str, defaultdict[tuple[int, int], CellValue]] = {}
        for sheet_name, filename in sheets.items():
            workbook[sheet_name] = defaultdict(
                str,
                (
                    (
                        parse_cell_reference(el.get("r", "")),
                        _primitive_to_value(el, shared_strings, style_number_formats),
                    )
                    for el in xq(filename, "./{*}sheetData/{*}row/{*}c")
                ),
            )
        return workbook


def write(
    file: Union[str, os.PathLike[str], IO[bytes]],
    data: Mapping[str, Iterable[tuple[tuple[int, int], CellValue]]],
    styler: Callable[[CellStyle, str, int, int, CellValue], object] = lambda *_: None,
) -> None:
    """向指定的文件中写出Excel 2007工作簿。

    数据由从工作表名到内容的映射给出，内容类似numpy.ndenumerate产生的迭代器，只要能被下列代码输出即可。

        for sheet_name in data:
            print("【工作表", sheet_name, "】")
            for (i, j), cell in data[sheet_name]:
                print("第", i, "行第", j, "列的数据是", cell)

    因此，根据使用需求不同，数据可以以各种结构存放，交给本函数的用户决定。

    如果数据是二维列表，那么像下面这样调用。

        sheet = [["A1", "B1"], ["A2", "B2"]]
        xlsx.write("output.xlsx", {
            "Sheet1": (
                ((i, j), cell)
                for i, row in enumerate(sheet)
                for j, cell in enumerate(row)
            ),
        })

    如果数据是二维字典，那么像下面这样调用。
    Excel要求单元格必须按顺序写入，否则认为文件损坏。
    如果能确保字典键按顺序排列，则可删去sorted。

        sheet = {0: {0: "A1", 1: "B1"}, 1: {0: "A2", 1: "B2"}}
        xlsx.write("output.xlsx", {
            "Sheet1": (
                ((i, j), cell)
                for i, row in sorted(sheet.items())
                for j, cell in sorted(row.items())
            ),
        })

    如果数据是复合键字典，那么像下面这样调用。
    同样，如果能确保字典键按顺序排列，则可删去sorted。

        sheet = {(0, 0): "A1", (0, 1): "B1", (1, 0): "A2", (1, 1): "B2"}
        xlsx.write("output.xlsx", {"Sheet1": sorted(sheet.items())})

    如果数据是NumPy数组，那么像下面这样调用。

        sheet = np.array([["A1", "B1"], ["A2", "B2"]])
        xlsx.write("output.xlsx", {"Sheet1": np.ndenumerate(sheet)})

    通过styler来程序化地指定单元格的样式。传入的函数如下述。

        def styler(style: CellStyle, sheet_name: str, row: int, column: int, value: CellValue):
            # 示例：设置B列为粗体、深蓝色字、浅蓝色背景。
            if column == 1:
                style.bold = True
                style.color = (0x12, 0x34, 0x56)
                style.fill = (0xab, 0xcd, 0xef)

    因为并不知道styler会在哪些单元格设置格式，实际只能指定指定了内容的单元格的样式。
    当然，可以通过指定单元格内容为空字符串来提示需要在对应单元格上执行styler。
    sheet_name还会传入空字符串，row、column参数还会传入−1。这时需要返回工作簿、行、列等的默认样式。
    """
    # 接下来将会多次出现的r:id="rId×××"并不是只有这一种固定格式。
    # OOXML是通过像Java那样狂写XML配置来表明文件之间关联的。
    # 因此，只要引用标识符一致性正确，理论上文件名随便是什么都没问题。
    # 然而，第三方软件完全不理解这一点，直接使用文件名和关系ID的索引来分析文件的库不在少数——本模块也是。
    # 为了尽可能兼容，还是按照Office的所作所为来做比较好。

    # https://insutanto.net/tag/Excel
    # https://zhuanlan.zhihu.com/p/386085542

    with zipfile.ZipFile(file, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
    %s
    <Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
    <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml" />
</Types>"""
            % "".join(
                f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                for i in range(1, len(data) + 1)
            ),
        )

        zf.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        )

        zf.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
    <workbookPr/>
    <sheets>
        %s
    </sheets>
    <calcPr calcId="114514"/>
</workbook>"""
            % "".join(
                f'<sheet name="{sheet_name}" sheetId="{i}" r:id="rId{i}"/>'
                for i, sheet_name in enumerate(data, 1)
            ),
        )

        # 即使是只用到一次的字符串也会存在共享字符串池中，未见有文件用单元格类型t="inlineStr"。
        shared_strings: defaultdict[str, int] = pool()

        cell_style = CellStyle()
        number_formats: defaultdict[str, int] = pool(176)  # 小索引都被Excel自带的数值格式占掉了
        number_formats |= {v: k for k, v in NUMBER_FORMATS.items()}
        fonts: defaultdict[str, int] = pool()
        fills: defaultdict[str, int] = pool(2)  # 似乎0号和1号填充被占用了，必须填充垃圾样式
        borders: defaultdict[str, int] = pool(1)  # 这个大概也有问题，保险起见填个垃圾再说
        cell_xfs: defaultdict[tuple[int, int, int, int], int] = pool()

        def style(sheet_name: str, i: int, j: int, value: CellValue) -> int:
            cell_style.reset()
            cell_style.number_format = (
                _value_to_cell(value, shared_strings)[0] or cell_style.number_format
            )
            styler(cell_style, sheet_name, i, j, value)
            return cell_xfs[
                number_formats[cell_style.number_format],
                fonts[cell_style.font_spec()],
                fills[cell_style.fill_spec()],
                borders[cell_style.border_spec()],
            ]

        # 将默认样式作为初始项目填入cell_xfs。
        style("", -1, -1, None)

        for sheet_id, (sheet_name, sheet) in enumerate(data.items(), 1):
            default_style = style(sheet_name, -1, -1, None)
            default_width = cell_style.width
            xml_head = f"""<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheetFormatPr customHeight="1" defaultRowHeight="{cell_style.height}" defaultColWidth="{default_width}"/>
<cols>"""
            xml_body = "</cols><sheetData>"
            columns = {16384: ""}
            old_i = -1
            for i, row in groupby(sheet, lambda x: x[0][0]):
                if i <= old_i:
                    raise ValueError("单元格行号应已排序")
                if i >= 1048576:
                    raise ValueError("超出范围的单元格")
                xml_body += f'<row r="{i + 1}" s="{style(sheet_name, i, -1, None)}" customFormat="1" ht="{cell_style.height}" customHeight="1">'
                old_j = -1
                for (_, j), cell in row:
                    if j <= old_j:
                        raise ValueError("一行中的单元格应按列号排序")
                    if j >= 16384:
                        raise ValueError("超出范围的单元格")
                    old_j = j
                    if j not in columns:
                        columns[
                            j
                        ] = f'<col min="{j + 1}" max="{j + 1}" style="{style(sheet_name, -1, j, None)}" width="{cell_style.width}" customWidth="1"/>'
                    xml_body += f'<c r="{column_number_to_letter(j)}{i + 1}" s="{style(sheet_name, i, j, cell)}" {_value_to_cell(cell, shared_strings)[1]}</c>'
                xml_body += "</row>"
            old_j = -1
            for j in sorted(columns):
                if j != old_j + 1:
                    xml_head += f'<col min="{old_j + 2}" max="{j}" style="{default_style}" width="{default_width}" customWidth="1"/>'
                xml_head += columns[j]
            zf.writestr(
                f"xl/worksheets/sheet{sheet_id}.xml",
                xml_head + xml_body + "</sheetData></worksheet>",
            )

        # rId1..rId(N) = 工作表。
        # rId(N+1) = 共享字符串池。
        # rId(N+2) = 样式表。
        # sheets first for rId# then theme > styles > sharedStrings
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    %s
    <Relationship Target="sharedStrings.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Id="rId%d"/>
    <Relationship Target="styles.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Id="rId%d"/>
</Relationships>"""
            % (
                "".join(
                    f'<Relationship Target="worksheets/sheet{i}.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Id="rId{i}"/>'
                    for i in range(1, len(data) + 1)
                ),
                len(data) + 1,
                len(data) + 2,
            ),
        )

        # 最后写入共享字符串池和样式表，因为在写入其他组件时会更新这些表。
        zf.writestr(
            "xl/sharedStrings.xml",
            # 如果不设置xml:space="preserve"的话，字符串中的前导和尾随空格会被XML解析器吞掉。
            # 设置了就一定有用吗？
            """<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<sst uniqueCount="%d" count="%d" xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xml:space="preserve">%s</sst>"""
            % (
                len(shared_strings),
                len(shared_strings),
                "".join(
                    f"<si><t>{html.escape(val)}</t></si>" for val in shared_strings
                ),
            ),
        )

        zf.writestr(
            "xl/styles.xml",
            """<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
    <numFmts>%s</numFmts>
    <fonts>%s</fonts>
    <fills>
        <fill><patternFill patternType="none"/></fill>
        <fill><patternFill patternType="gray125"/></fill>
        %s
    </fills>
    <borders>
        <border/>
        %s
    </borders>
    <cellStyleXfs>%s</cellStyleXfs>
    <cellXfs>%s</cellXfs>
    <cellStyles>
        <cellStyle name="a" xfId="0" builtinId="0" customBuiltin="1"/>
    </cellStyles>
</styleSheet>"""
            % (
                "".join(
                    f'<numFmt numFmtId="{i}" formatCode="{html.escape(number_format)}"/>'
                    for number_format, i in number_formats.items()
                    if i >= 128
                ),
                "".join(fonts),
                "".join(fills),
                "".join(borders),
                # cellStyleXfs中的第0项是所有工作表单元格的默认样式。
                "".join(
                    f'<xf numFmtId="{number_format}" fontId="{font}" fillId="{fill}" borderId="{border}"/>'
                    for number_format, font, fill, border in cell_xfs
                ),
                "".join(
                    f'<xf xfId="{i}" numFmtId="{number_format}" fontId="{font}" fillId="{fill}" borderId="{border}"/>'
                    for i, (number_format, font, fill, border) in enumerate(cell_xfs)
                ),
            ),
        )


def _value_to_cell(
    x: CellValue, shared_strings: Mapping[str, int]
) -> tuple[Optional[str], str]:
    """转换Python数据到单元格数值格式和SpreadsheetML <c>节点的属性和内容。

    对单元格格式没有特殊要求时返回None。返回值的XML片段应该嵌入在"<c "和"</c>"之间。
    """
    if x is None:
        # 空白单元格表示空字符串，所以必须另寻空值的表示。
        # #N/A表示空值是贴切的。只有数据科学家才用NaN表示缺损数据。
        # #NULL!是异常，类似计算min([])时发生的ValueError，不应采用。
        return None, 't="e"><v>#N/A</v>'
    elif isinstance(x, str):
        # 字符串会自动加入到共享字符串池。
        return None, f't="s"><v>{shared_strings[x]}</v>'
    elif isinstance(x, bytes):
        return "\"bytes\"('@')", f't="s"><v>{shared_strings[x.hex(" ").upper()]}</v>'
    elif isinstance(x, bool):
        # 布尔值，用0和1表示。
        return None, f't="b"><v>{x:d}</v>'
    elif isinstance(x, float) and math.isnan(x):
        # 借用#NUM!表示NaN。
        return None, f't="e"><v>#NUM!</v>'
    elif isinstance(x, float) and math.isinf(x):
        # 借用#DIV/0!表示无穷大。
        # 实际上Excel中=0/0会被计算为#DIV/0!（应为NaN），而=114^514会被计算为#NUM!（应为+∞）。
        # 不要在意这些细节。
        return None, f't="e"><v>#DIV/0!</v>'
    elif isinstance(x, datetime.datetime):
        return "yyyy-mm-dd hh:mm:ss", f"><v>{(x - EPOCH).total_seconds() / 86400}</v>"
    elif False:
        # 写入公式的话，要用<f>节点。<v>也能出现，用来缓存上回计算结果。
        # 能坚持不重算的程度还和工作簿的calcId有关。
        # 不过并没有加入公式支持的打算。
        return None, f"><f>{html.escape(...)}</f>"
    else:
        # 常规数值，类型省略。
        return None, f"><v>{x}</v>"
    # 顺便介绍一下剩下的Excel异常。
    # #NAME?对应NameError。
    # #REF!用C语言的话来说就是use after free。Python也有意思很接近的ReferenceError。
    # 带有垃圾回收机制的Python对象为什么也会在释放后又被使用？原因是弱引用，参照weakref标准库模块。
    # #VALUE!对应TypeError，不是ValueError。
    # #GETTING_DATA大概是正在从外部数据源获取数据时的占位值。
    # 介绍Excel的文章一般会用公式=NA()来人为制造一个空值。
    # 其实直接在单元格中输入“#N/A”就能创建空值。而且，其他类型的错误值也都能用直接输入的方式创造出来。
    # 这些值还能作为字面量在公式中导致报错，例如=IF(A1>0,A1-1,#NUM!)。Excel，很神奇吧？


def _cell_to_primitive(el: ET.Element, shared_strings: list[str]) -> CellPrimitive:
    """转换<c>元素到Python数据。"""
    t = el.get("t")
    value = el.find("./{*}v")
    value = value.text or "" if value is not None else ""
    formula = el.find("./{*}f")
    formula = formula.text or "" if formula is not None else ""

    if t == "s":
        return shared_strings[int(value)]
    elif t == "b":
        return value != "0"
    elif t == "str" or not value:
        # str类型表示公式计算结果是字符串类型，值不经过共享字符串池。
        # 空白单元格以空字符串表示。
        # 有时会有只有样式（s属性）的单元格，也按此处理。
        pass
    elif t == "e":
        if value == "#N/A":
            return None
        else:
            return math.nan
    else:
        return float(value)


def _primitive_to_value(
    el: ET.Element, shared_strings: list[str], style_number_formats: list[str]
) -> CellValue:
    """从单元格数值格式解析原始Python数据到复杂数据。"""
    value = _cell_to_primitive(el, shared_strings)
    number_format = style_number_formats[int(el.get("s", "0"))]
    if number_format.startswith('"') and '"(' in number_format:
        f = number_format.removeprefix('"').partition('"(')[0]
        if f == "bytes" and isinstance(value, str):
            return bytes.fromhex(value)
    # 删除段开头的方括号表达式，这可能包括货币和语言选项、特殊数字格式、颜色等。
    # 转义是简单替换：例如，"\\\"表示显示三个反斜杠，"\"\"表示显示一个反斜杠和一个引号。
    format_codes = re.sub(
        r'(^|(?<=;))(\[[^\[\]]+\])+|[\\_].|"[^"]*"|[-+$/():!^&\'~{}<>= ]+',
        "",
        number_format.casefold(),
    )
    while format_codes.endswith(";general"):
        format_codes = format_codes.removesuffix(";general")
    if format_codes == "general":
        format_codes = ""
    if (
        isinstance(value, float)
        and math.isfinite(value)
        and "." not in format_codes
        and ("0" in format_codes or "#" in format_codes)
    ):
        return int(value)
    if (
        isinstance(value, float)
        and value >= 0
        and re.search(r"[ymdhsgebวดปชนท]", format_codes, re.IGNORECASE)
    ):
        return EPOCH + datetime.timedelta(value)
    return value


def f(style: CellStyle, sheet_name: str, i, j, x):
    if sheet_name.endswith("0"):
        style.border_diagonal_up = True
        style.border_diagonal_style = "thick"
        style.border_diagonal_color = "#987654"
    style.fill = "#abcdef" if type(x) is str else "#114514"
    style.bold = i == 12
    if i == 12:
        style.height = 24
    if j == 6:
        style.width = 114
    style.border_bottom_color = "#e9e981"
    style.border_bottom_style = "thick"


if __name__ == "__main__":
    write(
        "output.xlsx",
        {
            "工作表114514": sorted(
                {
                    (12, 6): "妙的",
                    (12, 1): "不妙的",
                    (12, 7): 114.514,
                    (12, 4): math.inf,
                    (11, 2): "妙的",
                    (11, 3): "不妙的",
                    (11, 4): 114.514,
                    (11, 5): math.nan,
                    (13, 7): b"BYTES\0--in excel!",
                    (13, 8): datetime.datetime(1919, 8, 10, 11, 45, 14),
                }.items()
            ),
            "工作表1919810": (),
        },
        f,
    )
    from pprint import pprint
    from timeit import timeit

    pprint(read("output.xlsx"))
