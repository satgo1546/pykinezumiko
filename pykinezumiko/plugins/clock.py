import re
import os
import time
import pickle
from queue import PriorityQueue
import pykinezumiko


class Clock(pykinezumiko.Plugin):
    def __init__(self) -> None:
        super().__init__()
        # 存储路径
        self.path = 'logs/20clock.pickle'
        # 提醒队列
        t = []
        if os.path.isfile(self.path):
            with open(self.path, 'rb') as f:
                t = pickle.load(f)
        self.pq = PriorityQueue()
        for l in t:
            self.pq.put(l)

    def on_message(self, context: int, sender: int, text: str, message_id: int):
        if text.startswith(".clock"):
            # ".clock 增加的时间 消息" or ".clock 消息 增加的时间"
            dtAndTitle = text[7:].strip()
            # 匹配开头和结尾作为时间输入
            title, dt = None, None
            res = re.search(r"^\d+|\d+$", dtAndTitle)
            if not res:
                return "无法识别到有效时间"
            else:
                l, r = res.span()
                dt = int(res.group())
                title = dtAndTitle[:l] + dtAndTitle[r:]
                title = title.strip()
                if not title:
                    return "标题不能为空"

            # 存储格式：[浮点触发时间戳，回复内容，会话id]
            self.pq.put([time.time()+dt, title, context])
            with open(self.path, 'wb') as f:
                pickle.dump(list(self.pq.queue), f)
            return str(time.time()+dt) + " "+title

    def on_interval(self):
        # 如果提醒队列非空且第一个提醒到时间了就提醒用户
        while not self.pq.empty() and self.pq.queue[0][0] < time.time():
            _, title, target = self.pq.get()
            with open(self.path, 'wb') as f:
                pickle.dump(list(self.pq.queue), f)
            self.send(target, title)
            time.sleep(1)
