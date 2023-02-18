"""为了支持Python 3.9，补充新版标准库才有的功能。

古代的软件版本管理太恐怖了……
"""

from typing import (
    Iterable,
    Iterator,
    TypeVar,
    Any,
    Protocol,
    Union,
    Sequence,
    Optional,
    Callable,
    overload,
)
from itertools import tee
import bisect

T = TypeVar("T")


class SupportsDunderLT(Protocol):
    def __lt__(self, __other: Any) -> Any:
        ...


class SupportsDunderGT(Protocol):
    def __gt__(self, __other: Any) -> Any:
        ...


SupportsRichComparison = Union[SupportsDunderLT, SupportsDunderGT]
SupportsRichComparisonT = TypeVar(
    "SupportsRichComparisonT", bound=SupportsRichComparison
)


class BisectWrapper:
    def __init__(self, a, f):
        self.a = a
        self.f = f

    def __getitem__(self, i):
        return self.f(self.a[i])


@overload
def bisect_left(
    a: Sequence[SupportsRichComparisonT],
    x: SupportsRichComparisonT,
    lo: int = 0,
    hi: Optional[int] = None,
    *,
    key: None = None
) -> int:
    ...


@overload
def bisect_left(
    a: Sequence[T],
    x: SupportsRichComparisonT,
    lo: int = 0,
    hi: Optional[int] = None,
    *,
    key: Callable[[T], SupportsRichComparisonT]
) -> int:
    ...


def bisect_left(a, x, lo=0, hi=None, *, key=None) -> int:
    if key is None:
        return bisect.bisect_left(a, x, lo, hi)
    else:
        return bisect.bisect_left(BisectWrapper(a, key), x, lo, hi or len(a))  # type: ignore


@overload
def bisect_right(
    a: Sequence[SupportsRichComparisonT],
    x: SupportsRichComparisonT,
    lo: int = 0,
    hi: Optional[int] = None,
    *,
    key: None = None
) -> int:
    ...


@overload
def bisect_right(
    a: Sequence[T],
    x: SupportsRichComparisonT,
    lo: int = 0,
    hi: Optional[int] = None,
    *,
    key: Callable[[T], SupportsRichComparisonT]
) -> int:
    ...


def bisect_right(a, x, lo=0, hi=None, *, key=None) -> int:
    if key is None:
        return bisect.bisect_right(a, x, lo, hi)
    else:
        return bisect.bisect_right(BisectWrapper(a, key), x, lo, hi or len(a))  # type: ignore


def pairwise(iterable: Iterable[T]) -> Iterator[tuple[T, T]]:
    """为了支持Python 3.9，补一个itertools.pairwise……"""
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)
