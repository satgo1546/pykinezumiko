import time

from pykinezumiko import Event, Plugin


class 木鼠子(Plugin):
    def on_command_bot(self, event: Event):
        t = time.localtime()
        k = "〇一二三四五六七八九十"
        y = t.tm_year % 100
        m = t.tm_mon
        d = t.tm_mday
        y = k[y // 10] + k[y % 10]
        if m > 10:
            m = k[10] + k[m - 10]
        else:
            m = k[m]
        if d > 19:
            d = (k[d // 10] + k[10] + k[d % 10]).removesuffix(k[0])
        elif d > 10:
            d = k[10] + k[d - 10]
        else:
            d = k[d]
        return f"""木鼠子 ⅱ Python Ver. 基于 NapCat
「转义符
　是无声的响铃
　提示符
　是挂起的协程」
— Frog Chen, 2026
自豪地采用自研木鼠子码。破坏三层防御系统换来持续部署，隔离异步函数染色遗落现代诗歌。歌中蜃景如泡影溶解般从未存在，遍历文档却再难寻补不全的快乐。
今已处理消息 #TODO! 条。
书{y}年{m}月{d}日。"""
        # 做好日志之后做统计？

    on_command_about = on_command_bot
