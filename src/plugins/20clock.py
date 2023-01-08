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
            # .clock 50 v我50
            dtAndTitle = text.split(" ")[1:]
            dt = int(dtAndTitle[0])
            title = dtAndTitle[1]
            # 存储格式：[浮点触发时间戳，回复内容，会话id]
            self.q.append([time.time()+dt, title, context])
            return str(time.time()+dt)+" "+title

    def on_interval(self):
        # 如果提醒队列非空且第一个提醒到时间了就提醒用户
        while self.q and self.q[0][0] < time.time():
            title=self.q[0][1]
            self.send(self.q.pop()[2], title)
            time.sleep(1)
