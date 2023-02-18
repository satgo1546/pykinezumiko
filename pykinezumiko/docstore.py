"""一种很新的文档数据库对象-关系映射（ORM）。

所谓文档数据库，就是把数据存在Office文档里！
"""

import time
from collections.abc import KeysView, ValuesView, ItemsView
from itertools import count, takewhile
import typing
from typing import Any, Generator, Iterable, Protocol, TypeVar

try:
    from typing_extensions import dataclass_transform
except (ModuleNotFoundError, ImportError):
    if typing.TYPE_CHECKING:
        raise
    else:
        dataclass_transform = lambda **kwargs: lambda x: x

from . import xlsx

T = TypeVar("T")
T_contra = TypeVar("T_contra", contravariant=True)
TableT = TypeVar("TableT", bound="Table")


class Comparable(Protocol[T_contra]):
    def __lt__(self, __other: T_contra) -> bool:
        ...


ComparableT = TypeVar("ComparableT", bound=Comparable)
RecordT = TypeVar("RecordT", bound="Record")


@dataclass_transform(kw_only_default=True)
class Table(type):
    """记录的元类。

    TODO：最好画张类结构示意图！

    数据直接在内存中以索引到记录对象的**有序**映射存放。
    键保持有序是通过每次插入时全部重排实现的屑。

    Table元类因记录类实际保存数据、提供表中记录增删操作而得名。

    【问题】
    Table继承type，作为Record的元类，这样就能实现在记录类自身上使用标准下标语法操作表中记录。
    但是，正确标注类型极其困难。
    类型检查器偏好type而非其他元类，因此像下面这样使Table继承type的泛型也无济于事，T不知何所指。

        class Table(type[T]):
            def __getitem__(cls, key: str) -> T:
                ...

    https://discuss.python.org/t/metaclasses-and-typing/6983
    https://github.com/python/typing/issues/715

    现在只能做到外部使用基本没有问题。
    如你所见，类的内部一派混乱，强制无视类型错误的指令漫天飞舞。

    【已否决的设计】
    sortedcontainers提供的SortedDict性能更好。
    但反正现在每次操作完都会重新写入文件，内存中的操作摆烂也无所谓了。
    pandas的本质是平行数组，不适合单条记录的增删，所以不使用。

    在Record中添加类变量table: ClassVar[Table[KT, VT]]，其中Table是dict的子类。
    这样无法确定KT和VT。

    多重继承真的很糟糕。
    同时继承type和dict的话，会报基类间实例内存布局冲突错。
    同时继承type和UserDict或type和MutableMapping的话，isinstance将无法正常工作。
    但是，直接检查__class__仍然可行。
    因为类型标注比当前贫弱的解决方案更不充分，所以保持了手动实现各种dict方法的现状。

    既能使键类型成为泛型，又能正确获得元类产生的类的办法并不是没有。

        class Table(type[VT], UserDict[KT, VT], Generic[KT, VT]):
            def __getitem__(cls, key: KT) -> VT:
                ...
        class transformer(Generic[KT]):
            def __call__(self, cls: type[VT]) -> Table[KT, VT]:
                return Table(cls.__name__, cls.__bases__, cls.__dict__.copy())
        def record_type(key_type: type[KT]) -> transformer[KT]:
            return transformer()

        @record_type(key_type=int)
        class User:
            name: str

    但是这样会使@dataclass_transform()完全失效，无论加在哪里都无用。
    """

    dirty = False
    """插入记录、删除记录时自动置位。向记录对象写入属性时，也会写入此标志。"""

    def sort(cls) -> None:
        cls.table = dict(sorted(cls.table.items()))

    def __getitem__(cls: type[T], key: Comparable) -> T:
        return cls.table[key]  # type: ignore

    def __setitem__(cls: type[T], key: Comparable, value: T) -> None:
        if not cls.table or key in cls.table or next(reversed(cls.table)) < key:  # type: ignore
            cls.table[key] = value  # type: ignore
        else:
            cls.table[key] = value  # type: ignore
            cls.sort()  # type: ignore
        cls.dirty = True  # type: ignore

    def __delitem__(cls, key: Comparable) -> None:
        del cls.table[key]
        cls.dirty = True

    def keys(cls) -> KeysView[Comparable]:
        return cls.table.keys()  # type: ignore

    def values(cls: type[T]) -> ValuesView[T]:
        return cls.table.values()  # type: ignore

    def items(cls: type[T]) -> ItemsView[Comparable, T]:
        return cls.table.items()  # type: ignore

    def clear(cls) -> None:
        cls.table.clear()
        cls.dirty = True

    def update(cls: type[T], data: Iterable[tuple[Comparable, T]]) -> None:
        cls.table.update(data)  # type: ignore
        cls.sort()  # type: ignore
        cls.dirty = True  # type: ignore

    def __len__(self) -> int:
        return len(self.table)

    # TODO: def __iter__, pop, popitem, clear, update, setdefault, __contains__, get


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

    def __init__(self, filename: str, tables: tuple[TableT, ...]) -> None:
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
            field_types = typing.get_type_hints(table)
            # 注意Table没有__init__，table属性是在这里初始化的。
            table.table = {}
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
                    row = table()
                    for j, field in enumerate(fields):
                        # 迫使标有类型的字段值转换到标注的类型。仅适用于有单参数构造函数的数据类型。
                        cell = worksheet_data[i + 1, j + 1]
                        if not isinstance(cell, field_types.get(field, object)):
                            cell = field_types[field](cell)
                        setattr(row, field, cell)
                    table.table[worksheet_data[i + 1, 0]] = row
            table.dirty = False

    @property
    def dirty(self) -> bool:
        return any(table.dirty for table in self.tables)

    def worksheet_data(
        self, table: Table
    ) -> Generator[tuple[tuple[int, int], xlsx.CellValue], None, None]:
        fields = typing.get_type_hints(table)
        yield (0, 0), ""
        for j, field in enumerate(fields):
            yield (0, j + 1), field
        for i, (key, row) in enumerate(table.table.items()):
            yield (i + 1, 0), key
            for j, field in enumerate(fields):
                yield (i + 1, j + 1), getattr(row, field)

    def save(self) -> None:
        xlsx.write(
            self.filename,
            {table.__name__: self.worksheet_data(table) for table in self.tables},
        )
        for table in self.tables:
            table.dirty = False
