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
from typing import IO, Any, Callable, Literal, Union

CellPrimitive = Union[None, bool, int, float, str]
"""单元格值的类型。

无法区分整数和浮点数，NaN和无穷也无法准确存储。
"""

CellValue = Union[CellPrimitive, bytes]
"""通过单元格数值格式，额外支持的单元格值类型。"""

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
        self.color: str = "#000000"

        self.fill: str = "#ffffff"

        self.border_style = "none"
        self.border_color = "#000000"
        self.border_diagonal_down: bool = False
        self.border_diagonal_up: bool = False

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
    def border_color(self, color: str):
        self.border_top_color: str = color
        self.border_right_color: str = color
        self.border_bottom_color: str = color
        self.border_left_color: str = color
        self.border_diagonal_color: str = color

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
            + f'<color rgb="FF{self.color[-6:]}"/></font>'
        )

    def fill_spec(self) -> str:
        return f'<fill><patternFill patternType="solid"><fgColor rgb="FF{self.fill[-6:]}"/></patternFill></fill>'

    def border_spec(self) -> str:
        return (
            "<border"
            + (' diagonalUp="1"' if self.border_diagonal_up else "")
            + (' diagonalDown="1"' if self.border_diagonal_down else "")
            + f""">
<left style="{self.border_left_style}">
<color rgb="FF{self.border_left_color[-6:]}"/></left>
<right style="{self.border_right_style}">
<color rgb="FF{self.border_right_color[-6:]}"/></right>
<top style="{self.border_top_style}">
<color rgb="FF{self.border_top_color[-6:]}"/></top>
<bottom style="{self.border_bottom_style}">
<color rgb="FF{self.border_bottom_color[-6:]}"/></bottom>
<diagonal style="{self.border_diagonal_style}">
<color rgb="FF{self.border_diagonal_color[-6:]}"/></diagonal>
</border>"""
        )


EPOCH = datetime.date(1899, 12, 30)
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
) -> dict[str, defaultdict[tuple[int, int], CellPrimitive]]:
    """读取指定的工作簿。

    返回对象可以以下列形式使用：

        workbook = read("input.xlsx")
        worksheet = workbook["Sheet1"]
        cell = worksheet[8, 4]  # 第8行第4列，下标从0开始
        print("Sheet1!E9的值是", cell)
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

        # 读取工作表数据。
        workbook: dict[str, defaultdict[tuple[int, int], CellPrimitive]] = {}
        for sheet_name, filename in sheets.items():
            workbook[sheet_name] = defaultdict(
                str,
                (
                    (
                        parse_cell_reference(el.get("r", "")),
                        _cell_to_value(el, shared_strings),
                    )
                    for el in xq(filename, "./{*}sheetData/{*}row/{*}c")
                ),
            )
        return workbook


def write(
    file: Union[str, os.PathLike[str], IO[bytes]],
    data: Mapping[str, Iterable[tuple[int, Iterable[tuple[int, CellPrimitive]]]]],
    styler: Callable[
        [CellStyle, str, int, int, CellPrimitive], object
    ] = lambda *_: None,
) -> None:
    """向指定的文件中写出Excel 2007工作簿。

    数据由从工作表名到内容的映射给出，内容是嵌套的可迭代对象，只要能被下列代码输出即可。

        for sheet_name in data:
            print("【工作表", sheet_name, "】")
            for i, row in data[sheet_name]:
                for j, cell in row:
                    print("第", i, "行第", j, "列的数据是", cell)

    因此，根据使用需求不同，数据可以以各种结构存放，交给本函数的用户决定。

    如果数据是二维列表或二维NumPy数组，那么像下面这样调用。

        sheet = [["A1", "B1"], ["A2", "B2"]]
        xlsx.write("output.xlsx", {
            "Sheet1": ((i, enumerate(row)) for i, row in enumerate(sheet)),
        })

    如果数据是二维字典，那么像下面这样调用。键不必按顺序排列。

        sheet = {0: {0: "A1", 1: "B1"}, 1: {0: "A2", 1: "B2"}}
        xlsx.write("output.xlsx", {
            "Sheet1": ((i, row.items()) for i, row in sheet.items()),
        })

    如果数据是复合键字典，那么像下面这样调用。因为必须整行写入，所以使用了sorted和groupby。

        sheet = {(0, 0): "A1", (0, 1): "B1", (1, 0): "A2", (1, 1): "B2"}
        from itertools import groupby
        xlsx.write("output.xlsx", {
            "Sheet1": (
                (i, ((j, sheet[i, j]) for i, j in row))
                for i, row in groupby(sorted(sheet), lambda x: x[0])
            ),
        })

    通过styler来程序化地指定单元格的样式。只能指定指定了内容的单元格的样式。传入的函数如下述。

        def styler(sheet_name: str, row: int, column: int, value: CellValue):
            number_format = "General"
            font = ""
            fill = ""
            border = ""
            # 示例：设置B列为粗体、深色2
            if column == 1:
                font = '<b/><color theme="3"/>'
                fill = '<patternFill patternType="solid"><fgColor theme="0"/></patternFill>'
            return number_format, font, fill, border
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
        style = CellStyle()
        number_formats: defaultdict[str, int] = pool(176)  # 小索引都被Excel自带的数值格式占掉了
        number_formats["General"] = 0
        fonts: defaultdict[str, int] = pool()
        fills: defaultdict[str, int] = pool(2)  # 似乎0号和1号填充被占用了，必须填充垃圾样式
        borders: defaultdict[str, int] = pool(1)  # 不知道这个有没有问题，保险起见填个垃圾再说
        cell_xfs: defaultdict[tuple[int, int, int, int], int] = pool()
        for shID, (sheet_name, sheet) in enumerate(data.items(), 1):
            with zf.open(f"xl/worksheets/sheet{shID}.xml", "w") as f:
                f.write(
                    b"""<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
    <sheetFormatPr customHeight="1" defaultRowHeight="20" defaultColWidth="6"/>
    <cols>
        <col customWidth="1" min="1" max="1" width="4.25"/>
        <col customWidth="1" min="2" max="2" width="11.13"/>
        <col customWidth="1" min="3" max="3" width="27.75"/>
        <col customWidth="1" min="4" max="4" width="12.13"/>
        <col customWidth="1" min="5" max="6" width="12.5"/>
        <col customWidth="1" min="7" max="7" width="8.63"/>
        <col customWidth="1" min="9" max="68" width="3.0"/>
        <col customWidth="1" min="69" max="69" width="3.38"/>
    </cols>
    <sheetData>"""
                )
                for i, row in sheet:
                    f.write(f'<row r="{i + 1}">'.encode())
                    for j, cell in row:
                        style.reset()
                        styler(style, sheet_name, i, j, cell)
                        s = cell_xfs[
                            number_formats[style.number_format],
                            fonts[style.font_spec()],
                            fills[style.fill_spec()],
                            borders[style.border_spec()],
                        ]
                        f.write(
                            f'<c r="{column_number_to_letter(j)}{i + 1}" s="{s}" {_value_to_cell(cell, shared_strings)}</c>'.encode()
                        )
                    f.write(b"</row>")
                f.write(b"</sheetData></worksheet>")

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
    <cellStyleXfs>
        <xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
    </cellStyleXfs>
    <cellXfs>%s</cellXfs>
</styleSheet>"""
            % (
                "".join(
                    f'<numFmt numFmtId="{i}" formatCode="{html.escape(number_format)}"/>'
                    for number_format, i in number_formats.items()
                    if i
                ),
                "".join(fonts),
                "".join(fills),
                "".join(borders),
                "".join(
                    f'<xf xfId="0" numFmtId="{number_format}" fontId="{font}" fillId="{fill}" borderId="{border}"/>'
                    for number_format, font, fill, border in cell_xfs
                ),
            ),
        )


def _value_to_cell(x: CellPrimitive, shared_strings: Mapping[str, int]) -> str:
    """转换Python数据到SpreadsheetML <c>节点的属性和内容。

    返回值应该嵌入在"<c "和"</c>"之间。
    """
    if x is None:
        # 空白单元格表示空字符串，所以必须另寻空值的表示。
        # #N/A表示空值是贴切的。只有数据科学家才用NaN表示缺损数据。
        # #NULL!是异常，类似计算min([])时发生的ValueError，不应采用。
        return 't="e"><v>#N/A</v>'
    elif isinstance(x, str):
        # 字符串会自动加入到共享字符串池。
        return f't="s"><v>{shared_strings[x]}</v>'
    elif isinstance(x, bytes):
        "0;0;0;\"bytes\"('@')"
        return f't="s"><v>{shared_strings[repr(x)[2:-1]]}</v>'
    elif isinstance(x, bool):
        # 布尔值，用0和1表示。
        return f't="b"><v>{x:d}</v>'
    elif isinstance(x, float) and math.isnan(x):
        # 借用#NUM!表示NaN。
        return f't="e"><v>#NUM!</v>'
    elif isinstance(x, float) and math.isinf(x):
        # 借用#DIV/0!表示无穷大。
        # 实际上Excel中=0/0会被计算为#DIV/0!（应为NaN），而=114^514会被计算为#NUM!（应为+∞）。
        # 不要在意这些细节。
        return f't="e"><v>#DIV/0!</v>'
    elif False:
        # 写入公式的话，要用<f>节点。<v>也能出现，用来缓存上回计算结果。
        # 能坚持不重算的程度还和工作簿的calcId有关。
        # 不过并没有加入公式支持的打算。
        return f"><f>{html.escape(...)}</f>"
    else:
        # 常规数值，类型省略。
        return f"><v>{x}</v>"
    # 顺便介绍一下剩下的Excel异常。
    # #NAME?对应NameError。
    # #REF!用C语言的话来说就是use after free。Python也有意思很接近的ReferenceError。
    # 带有垃圾回收机制的Python对象为什么也会在释放后又被使用？原因是弱引用，参照weakref标准库模块。
    # #VALUE!对应TypeError，不是ValueError。
    # #GETTING_DATA大概是正在从外部数据源获取数据时的占位值。
    # 介绍Excel的文章一般会用公式=NA()来人为制造一个空值。
    # 其实直接在单元格中输入“#N/A”就能创建空值。而且，其他类型的错误值也都能用直接输入的方式创造出来。
    # 这些值还能作为字面量在公式中导致报错，例如=IF(A1>0,A1-1,#NUM!)。Excel，很神奇吧？


def _cell_to_value(el: ET.Element, shared_strings: list[str]) -> CellPrimitive:
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
    elif re.fullmatch(r"-?[0-9]+", value):
        return int(value)
    else:
        return float(value)


def f(style: CellStyle, sheet_name, i, j, x):
    style.fill = "#114514"
    style.border_bottom_color = "#e9e981"
    style.border_bottom_style = "thick"


write(
    "output.xlsx",
    {"工作表114514": {11: {2: "妙的", 3: "不妙的", 4: 114.514, 5: math.nan}.items()}.items()},
    f,
)
db = read("output.xlsx")
from pprint import pprint
from timeit import timeit

pprint(db["工作表114514"])
db = read("工作簿1.xlsx")
pprint(db["Sheet2"])