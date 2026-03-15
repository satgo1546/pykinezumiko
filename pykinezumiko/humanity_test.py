import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from .humanity import ellipsize, format_exception, normalize, parse_command, scrub, short


def test_scrub():
    assert scrub("") == ""
    assert scrub("\r\n\r\n") == "\n\n"
    assert scrub("\0\1\2\3\4\5\6\7") == ""
    assert scrub("\ufffe😾\udabc🐈‍⬛\uffff") == "😾🐈‍⬛"


class TestEllipsize:
    def test_基本功能(self):
        assert ellipsize("", 0) == ""
        assert ellipsize("", 114514) == ""
        assert ellipsize("114514", 0) == ""
        assert ellipsize("114514", 1) == "…"
        assert ellipsize("114514", 2) == "1…"
        assert ellipsize("114514", 3) == "11…"
        assert ellipsize("114514", 6) == "114514"
        assert ellipsize("114514", 7) == "114514"
        assert ellipsize("114514", 114514) == "114514"

    @given(st.text(alphabet=st.characters()), st.integers(min_value=0, max_value=10))
    def test_不变量(self, string, length):
        assert len(ellipsize(string, length)) <= length

    def test_不可切断字符(self):
        assert ellipsize("😾😾😾", 0) == ""
        assert ellipsize("😾😾😾", 1) == "…"
        assert ellipsize("😾😾😾", 2) == "😾…"
        assert ellipsize("😾😾😾", 3) == "😾😾😾"
        assert ellipsize("😾😾😾", 4) == "😾😾😾"
        assert ellipsize("Aa" + "\u0301" * 10, 7) == "A…"
        assert ellipsize("Aa" + "\u0301" * 100, 42) == "A…"
        assert ellipsize("🐈‍⬛😾🐈‍⬛", 3) == "…"
        assert ellipsize("🐈‍⬛😾🐈‍⬛", 4) == "🐈‍⬛…"
        assert ellipsize("🐈‍⬛😾🐈‍⬛", 5) == "🐈‍⬛😾…"
        assert ellipsize("🐈‍⬛😾🐈‍⬛", 6) == "🐈‍⬛😾…"


class TestShort:
    def test_基本功能(self):
        assert short("", 114) == ""
        assert short("114514", 114) == "114514"
        assert short("a" * 114, 114) == "a" * 114
        assert short("a" * 114, 16) == "aaaa ≪106≫ aaaa"
        assert short("a" * 1919, 16) == "aaaa ≪1911≫ aaaa"

    def test_不适用于长度限制较短的场合(self):
        with pytest.raises(ValueError):
            short("", 0)
        with pytest.raises(ValueError):
            short("", 1)
        with pytest.raises(ValueError):
            short("114514", 0)
        with pytest.raises(ValueError):
            short("114514", 4)

    def test_不可切断字符(self):
        assert short("😾" * 114, 16) == "😾😾😾😾 ≪106≫ 😾😾😾😾"
        assert short("😾" * 114, 18) == "😾😾😾😾😾 ≪104≫ 😾😾😾😾😾"
        assert short("🐈‍⬛" * 114, 16) == "🐈‍⬛ ≪336≫ 🐈‍⬛"
        assert short("🐈‍⬛" * 114, 18) == "🐈‍⬛ ≪336≫ 🐈‍⬛"
        assert short("😾🧑‍🧑‍🧒‍🧒😾🧑‍🧑‍🧒‍🧒😾", 16) == "😾 ≪15≫ 😾"

    @given(st.text(alphabet=st.characters()), st.integers(min_value=16, max_value=32))
    def test_不变量_长度限制(self, string, length):
        assert len(short(string, length)) <= length

    @given(st.text(alphabet=st.characters(), min_size=31), st.integers(min_value=16, max_value=30))
    def test_不变量_字符串内容(self, string, length):
        result = short(string, length)
        match = re.search(r" ≪\d+≫ ", result)
        assert match is not None
        i = match.start()
        j = match.end()
        assert string.startswith(result[:i])
        assert string.endswith(result[j:])


def test_normalize():
    assert normalize("test") == "test"
    assert normalize("😾") == "😾"
    assert normalize("ℹ\ufe0f") == "i"
    assert normalize("．ｔｅｓｔ") == "test"
    assert normalize("㎭𝕴㎈") == "radical"
    assert normalize("ℝ𝕒𝕕𝕚𝕔𝕒𝕝𝕝𝕪") == "radically"
    assert normalize("㎯") == "rad\N{DIVISION SLASH}s2"
    assert normalize("ﬃ") == "ffi"
    assert normalize("ﬀĲ") == "ffij"
    assert normalize("　Ｆ　Ｏ　Ｏ　Ｂ　Ａ　Ｒ　") == "foobar"
    assert normalize("Ḟṏȫḇẳṝ") == "foobar"
    assert normalize("ꞙꝏƀⱥꞧ") == "ꞙꝏƀⱥꞧ"


class TestParseCommand:
    COMMANDS = sorted(map(normalize, ["test", "radical", "F.F.I.", "foo", "foo bar", "abc"]))

    def test_命令前缀符号必须精确匹配(self):
        assert parse_command(".test", self.COMMANDS) == ("test", "")
        assert parse_command(" .test", self.COMMANDS) is None
        assert parse_command("．ｔｅｓｔ", self.COMMANDS) is None

    def test_二分边界场景(self):
        assert parse_command(".a", self.COMMANDS) is None
        assert parse_command(".z", self.COMMANDS) is None
        assert parse_command(".", [""]) == ("", "")
        assert parse_command(".a", [""]) == ("", "a")

    def test_二分命令名时切到代理对(self):
        # 继承自JavaScript测试集，不过在Python中BMP之外的字符不会带来特别的问题。
        assert parse_command(".㎭𝕴㎈", self.COMMANDS) == ("radical", "")
        assert parse_command(".ℝ𝕒𝕕𝕚𝕔𝕒𝕝𝕝𝕪", self.COMMANDS) == ("radical", "𝕝𝕪")

    def test_命令名取最短前缀(self):
        assert parse_command(".㎭𝕴㎈__xyz", self.COMMANDS) == ("radical", "__xyz")
        assert parse_command(".㎭·𝕴·㎈__xyz", self.COMMANDS) == ("radical", "__xyz")
        assert parse_command(".testarg", self.COMMANDS) == ("test", "arg")

    def test_命令名无视空格与标点符号(self):
        assert parse_command(".Fﬁ ", self.COMMANDS) == ("ffi", "")
        assert parse_command(". ﬀI ", self.COMMANDS) == ("ffi", "")
        assert parse_command(". F ﬁ ", self.COMMANDS) == ("ffi", "")
        assert parse_command(".__ffi__", self.COMMANDS) == ("ffi", "__")
        assert parse_command(". ﬀ---I.", self.COMMANDS) == ("ffi", ".")
        assert parse_command(".(ffi)", self.COMMANDS) is None

    def test_命令名必须可精确切下(self):
        assert parse_command(".FFĲ", self.COMMANDS) is None

    def test_不可切断字符(self):
        assert parse_command(".FFℹ\ufe0f", self.COMMANDS) == ("ffi", "")
        assert parse_command(".FFℹ\u0301\u0302\u0303X", self.COMMANDS) == ("ffi", "X")

    def test_解析剩余字符串不含空格(self):
        assert parse_command("! Ｆｏｏ  BÄR114514 ", self.COMMANDS) == ("foobar", "114514")


def test_format_exception():
    try:
        raise RuntimeError("😾")
    except Exception as e:
        assert re.fullmatch(
            r"来自 humanity_test.py:\d+:test_format_exception 的 RuntimeError：😾", format_exception(e)
        )

    def nested():
        raise RuntimeError("😾😾")

    try:
        nested()
    except Exception as e:
        assert re.fullmatch(r"来自 humanity_test.py:\d+:nested 的 RuntimeError：😾😾", format_exception(e))
