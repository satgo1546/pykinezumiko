import re

from .humanity import format_exception, normalize, parse_command, scrub


def test_scrub():
    assert scrub("") == ""
    assert scrub("\r\n\r\n") == "\n\n"
    assert scrub("\0\1\2\3\4\5\6\7") == ""
    assert scrub("\ufffe😾\udabc🐈‍⬛\uffff") == "😾🐈‍⬛"


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
