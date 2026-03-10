import re
from .humanity import format_exception


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
