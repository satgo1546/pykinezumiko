from typing import SupportsInt


def format_timespan(seconds: SupportsInt) -> str:
    r = []
    seconds = int(seconds)
    if seconds >= 86400:
        r.append(str(seconds // 86400))
        r.append("天")
    seconds %= 86400
    if seconds >= 3600:
        r.append(str(seconds // 3600))
        r.append("小时")
    seconds %= 3600
    if seconds >= 60:
        r.append(str(seconds // 60))
        r.append("分")
    seconds %= 60
    r.append(str(seconds))
    r.append("秒")
    return " ".join(r)
