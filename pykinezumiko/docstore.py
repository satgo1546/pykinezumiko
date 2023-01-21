"""一种很新的文档数据库对象-关系映射（ORM）。

所谓文档数据库，就是把数据存在Office文档里！
"""

from itertools import count, takewhile
import time
from typing import Any, Generator, TypeVar, get_type_hints
from collections.abc import ItemsView
from sortedcontainers import SortedDict

from . import xlsx

T = TypeVar("T")


class Table(type[T]):
    """记录的元类。

    TODO：最好画张类结构示意图！

    数据直接在内存中以索引到记录对象的**有序**映射存放。
    pandas的本质是平行数组，不适合单条记录的增删，所以不使用。
    Table元类因记录类实际保存数据、提供表中记录增删操作而得名。
    """

    def __init__(
        cls, name: str, bases: tuple[type, ...], attrs: dict[str, Any]
    ) -> None:
        cls._data = SortedDict()
        """在记录类中存放表数据。"""
        cls.dirty = False
        """插入记录、删除记录时自动置位。向记录对象写入属性时，也会写入此标志。"""

    def __getitem__(cls, key) -> T:
        return cls._data[key]

    def __setitem__(cls, key, value: T) -> None:
        if not isinstance(value, cls):
            raise TypeError(f"记录应是{cls}的实例")
        cls._data[key] = value
        cls.dirty = True

    def __delitem__(cls, key) -> None:
        del cls._data[key]
        cls.dirty = True

    def __len__(self) -> int:
        return len(self._data)

    def items(cls) -> ItemsView[Any, T]:
        return cls._data.items()

    def clear(cls) -> None:
        cls._data.clear()


class Record(metaclass=Table):
    def __init__(self, **kwargs) -> None:
        # 实际上这些属性赋值都会经过self.__setattr__。
        # 因为在__slots__中有特别判断，所以没有额外副作用。
        self.created_at = time.time()
        """创建记录对象的时间戳。"""
        self.updated_at = self.created_at
        """上一次设置属性的时间戳。"""
        self.__dict__.update(kwargs)

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        # 修改特殊属性不应导致其他特殊属性的变化。
        if name not in ("created_at", "updated_at"):
            self.updated_at = time.time()
        self.__class__.dirty = True


class Database:
    """Excel数据库。

    “他妈的，怎么是Excel？！”pickle、JSON、CSV、SQLite……样样总比Excel好——我一开始也是这样想的。
    在快速开发迭代的过程中，数据库表头（schema）变动是常有的事。
    如已存了一些数据，在正式的数据库中修改表头必须编写数据迁移脚本，非常不便。
    号称schemaless的文档数据库只不过是将所有字段设为可空，反而加重了数据读取端校验的负担。
    专用的二进制存储格式只有借助特制的工具才能打开，人工浏览困难重重。
    电子表格在这样的场合便利至极：查阅、筛选、统计都很轻松，迁移数据更是只需填充公式。
    Office文档虽然的的确确是堆烂格式，但是人人都在用，受到良好的支持。
    """

    def __init__(self, filename: str, tables: tuple[Table, ...]) -> None:
        self.filename = filename
        self.tables = tables
        self.reload()

    def reload(self):
        try:
            workbook_data = xlsx.read(self.filename)
        except FileNotFoundError:
            workbook_data = {}
        for table in self.tables:
            worksheet_data = workbook_data.get(table.__name__)
            table.clear()
            if worksheet_data:
                fields = list(
                    map(
                        str,
                        takewhile(bool, (worksheet_data[0, j + 1] for j in count())),
                    )
                )
                for i in count():
                    row = table()
                    for j, field in enumerate(fields):
                        setattr(row, field, worksheet_data[i + 1, j + 1])
                    table[worksheet_data[i + 1, 0]] = row
            table.dirty = False

    @property
    def dirty(self) -> bool:
        return any(table.dirty for table in self.tables)

    def worksheet_data(
        self, table: Table
    ) -> Generator[tuple[tuple[int, int], xlsx.CellValue], None, None]:
        fields = get_type_hints(table)
        yield (0, 0), ""
        for j, field in enumerate(fields):
            yield (0, j + 1), field
        for i, (key, row) in enumerate(table.items()):
            yield (i + 1, 0), key
            for j, field in enumerate(fields):
                yield (i + 1, j + 1), getattr(row, field)

    def save(self) -> None:
        xlsx.write(
            self.filename,
            {table.__name__: self.worksheet_data(table) for table in self.tables},
        )
