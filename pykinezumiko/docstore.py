"""一种很新的文档数据库对象-关系映射（ORM）。

所谓文档数据库，就是把数据存在Office文档里！
"""

import time
from itertools import count, takewhile
from typing import (
    Any,
    ClassVar,
    Generator,
    Generic,
    Mapping,
    Protocol,
    TypeVar,
    get_type_hints,
)
from typing_extensions import Self

from . import xlsx

T = TypeVar("T")
T_contra = TypeVar("T_contra", contravariant=True)
TableT = TypeVar("TableT", bound="Table")


class Comparable(Protocol[T_contra]):
    def __lt__(self, __other: T_contra) -> bool:
        ...


ComparableT = TypeVar("ComparableT", bound=Comparable)
RecordT = TypeVar("RecordT", bound="Record")


class Table(dict[ComparableT, RecordT]):
    """实际保存数据、提供记录增删操作、跟踪是否已修改的表。

    TODO：最好画张类结构示意图！

    数据直接在内存中以索引到记录对象的映射存放。
    键保持有序，而且是通过每次插入时全部重排实现的屑。

    sortedcontainers提供的SortedDict性能更好。
    但反正现在每次操作完都会重新写入文件，内存中的操作摆烂也无所谓了。
    pandas的本质是平行数组，不适合单条记录的增删，所以不使用。

    【已否决的设计】
    Table继承type，作为Record的元类，这样就能实现在记录类自身上使用标准下标语法操作表中记录。

        class Table(type):
            def __getitem__(cls, key):
                return self._data[key]
            ...
        class Record(metaclass=Table):
            ...
        class User(Record):
            name: str
        User[1] = User(name="A")
        User[1].name = "B"
        del User[1]

    但是，正确标注类型极其困难。
    因为下标运算符被占用，无法使Table或Record成为泛型。
    即使强加上键必须是字符串的无理要求，也只能做到这样的程度：

        class Table(type):
            def __getitem__(cls: type[T], key: str) -> T:
                ...

    然后，因type[T]不兼容Table而报错。

    类型检查器偏好type而非其他元类，因此像下面这样使Table继承type的泛型也无济于事。

        class Table(type[T]):
            def __getitem__(cls, key: str) -> T:
                ...

    T不知何所指。
    https://discuss.python.org/t/metaclasses-and-typing/6983
    https://github.com/python/typing/issues/715
    """

    def __init__(self) -> None:
        self.dirty: bool = False
        """插入记录、删除记录时自动置位。向记录对象写入属性时，也会写入此标志。"""

    def sort(self) -> None:
        for key in sorted(self):
            tmp = self[key]
            del self[key]
            self[key] = tmp

    def __setitem__(self, key: ComparableT, value: RecordT) -> None:
        if key in self or next(reversed(self)) < key:
            super().__setitem__(key, value)
        else:
            super().__setitem__(key, value)
            self.sort()
        self.dirty = True

    def __delitem__(self, key: ComparableT) -> None:
        super().__delitem__(key)
        self.dirty = True

    def __ior__(self: TableT, value: Mapping[ComparableT, RecordT]) -> TableT:
        self.update(value)
        self.sort()
        self.dirty = True
        return self


class Record():
    @classmethod
    @property
    def table(cls:type[RecordT])->Table[str,RecordT]:
        return Table()

    @table.setter
    def set_table(self):
        return
    #table: ClassVar[Table[ComparableT, RecordT]]

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
        self.table.dirty = True


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

    def __init__(self, filename: str, record_types: tuple[type[Record], ...]) -> None:
        self.filename = filename
        self.record_types = record_types
        self.reload()

    def reload(self):
        try:
            workbook_data = xlsx.read(self.filename)
        except FileNotFoundError:
            workbook_data = {}
        for record_type in self.record_types:
            worksheet_data = workbook_data.get(record_type.__name__)
            record_type.table = Table()
            if worksheet_data:
                fields = list(
                    map(
                        str,
                        takewhile(bool, (worksheet_data[0, j + 1] for j in count())),
                    )
                )
                for i in count():
                    if worksheet_data[i + 1, 0] == "":
                        break
                    row = record_type()
                    for j, field in enumerate(fields):
                        setattr(row, field, worksheet_data[i + 1, j + 1])
                    record_type.table[worksheet_data[i + 1, 0]] = row
            record_type.table.dirty = False

    @property
    def dirty(self) -> bool:
        return any(record_type.table.dirty for record_type in self.record_types)

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
            {
                record_type.__name__: self.worksheet_data(record_type.table)
                for record_type in self.record_types
            },
        )
