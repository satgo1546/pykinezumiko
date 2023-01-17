import html
import math
import os
import re
import zipfile
from collections.abc import Iterable, Mapping
from datetime import datetime
from functools import reduce
from typing import IO, Union

EPOCH = datetime(1899, 12, 30)
CellValue = Union[None, bool, int, float, str]


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


def write(
    file: Union[str, os.PathLike[str], IO[bytes]],
    data: Mapping[str, Iterable[tuple[int, Iterable[tuple[int, CellValue]]]]],
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
    """
    # 接下来将会多次出现的r:id="rId×××"并不是只有这一种固定格式。
    # OOXML是通过像Java那样狂写XML配置来表明文件之间关联的。
    # 然而，第三方软件完全不理解这一点，直接使用文件名和关系ID的索引来分析文件的库不在少数。
    # 为了尽可能兼容，还是按照Office的所作所为来做比较好。

    # https://insutanto.net/tag/Excel
    # https://zhuanlan.zhihu.com/p/386085542

    # 共享字符串池是从字符串到加入顺序（从0开始）的映射。
    # 因为找不到字符串时就加入，且从不删除条目，所以满足以下不变量，即字典值是从0开始按顺序的连续整数。
    #     list(shared_strings.values()) == list(range(len(shared_strings)))
    shared_strings: dict[str, int] = {}

    with zipfile.ZipFile(file, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
    %s
    <Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
</Types>"""
            % "".join(
                f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                for i in range(1, len(data) + 1)
            ),
        )

        zf.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        )

        zf.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
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

        for shID, sheet in enumerate(data.values(), 1):
            with zf.open(f"xl/worksheets/sheet{shID}.xml", "w") as f:
                f.write(
                    b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
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
                        f.write(
                            f'<c r="{column_number_to_letter(j)}{i + 1}" {_value_to_cell(cell, shared_strings)}</c>'.encode()
                        )
                    f.write(b"</row>")
                f.write(b"</sheetData></worksheet>")

        # rId1..rId(N) = 工作表。
        # rId(N+1) = 共享字符串池。
        # sheets first for rId# then theme > styles > sharedStrings
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    %s
    <Relationship Target="sharedStrings.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Id="rId%d"/>
</Relationships>"""
            % (
                "".join(
                    f'<Relationship Target="worksheets/sheet{i}.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Id="rId{i}"/>'
                    for i in range(1, len(data) + 1)
                ),
                len(data) + 1,
            ),
        )

        # 最后写入共享字符串池，因为在写入其他组件时会更新共享字符串池。
        # 如果不设置xml:space="preserve"的话，字符串中的前导和尾随空格会被XML解析器吞掉。
        zf.writestr(
            "xl/sharedStrings.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<sst uniqueCount="%d" count="%d" xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xml:space="preserve">%s</sst>"""
            % (
                len(shared_strings),
                len(shared_strings),
                "".join(
                    f"<si><t>{html.escape(val)}</t></si>" for val in shared_strings
                ),
            ),
        )


def _value_to_cell(x: CellValue, shared_strings: dict[str, int]) -> str:
    """转换Python数据到SpreadsheetML <c>节点的属性和内容。

    返回值应该嵌入在"<c "和"</c>"之间。
    """
    if x is None:
        # 空白单元格表示空字符串，所以必须另寻空值的表示。
        # #N/A表示空值是贴切的。只有数据科学家才用NaN表示缺损数据。
        # #NULL!是异常，类似计算min([])时发生的ValueError，不应采用。
        return 't="e"><v>#N/A</v>'
    elif isinstance(x, str):
        # 字符串要加入到共享字符串池。
        if x not in shared_strings:
            shared_strings[x] = len(shared_strings)
        return f't="s"><v>{shared_strings[x]}</v>'
    elif isinstance(x, bool):
        # 布尔值。
        return f't="b"><v>{x}</v>'
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


write("output.xlsx", {"工作表114514": {11: {2: "妙的", 3: "不妙的"}.items()}.items()})
