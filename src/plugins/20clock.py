import time
import collections
from .. import ChatbotBehavior


class Clock(ChatbotBehavior):
    def __init__(self) -> None:
        super().__init__()
        # 提醒队列
        self.q = collections.deque()

    def on_message(self, context: int, sender: int, text: str, message_id: int):
        if text.startswith(".clock"):
            # ".clock 增加的时间 消息" or ".clock 消息 增加的时间"
            dtAndTitle = text.split(" ")[1:]
            # 1 匹配开头作为时间输入
            dt, title = None, " ".join(dtAndTitle[1:])
            # 匹配int数字
            if dtAndTitle[0].isdigit():
                dt = int(dtAndTitle[0])
            # 2 匹配结尾作为时间输入
            title = " ".join(dtAndTitle[:-1])
            # 匹配int数字
            if dtAndTitle[-1].isdigit():
                dt = int(dtAndTitle[-1])
            # 存储格式：[浮点触发时间戳，回复内容，会话id]
            if dt:
                self.q.append([time.time()+dt, title, context])
                return str(time.time()+dt)+" "+title
            else:
                return "无法识别到有效时间"

    def on_interval(self):
        # 如果提醒队列非空且第一个提醒到时间了就提醒用户
        while self.q and self.q[0][0] < time.time():
            title = self.q[0][1]
            self.send(self.q.popleft()[2], title)
            time.sleep(1)
