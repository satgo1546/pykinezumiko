import time
from collections import OrderedDict
from collections.abc import Generator
from typing import Any, ClassVar, Optional, Union, overload

import requests


class ChatbotBehavior:
    """所有插件的基类。

    继承此类且没有子类的类将自动被视为插件而实例化。
    通过覆盖以“on_”开头的方法，可以监听事件。
    因为这些方法都是空的，不必在覆盖的方法中调用super。
    可以在事件处理中调用messenger模块中的方法来作出行动。

    事件包含整数型的context和sender参数。
    正数表示好友，负数表示群。
    context表示消息来自哪个会话。要回复的话请发送到这里。
    sender表示消息的发送者。除了少数无来源的群通知事件，都会是正值。
    例如，私聊的场合，有context == sender > 0；群聊消息则满足context < 0 < sender。

    通常，当插件处理了事件（例如回复了消息），就要返回真值。
    为方便计，可以直接返回要回复的文字（类型是str），与执行send函数无异。
    返回假值（即None、False、""）的场合，表示插件无法处理这个事件。该事件会轮替给下一个插件来处理。
    """

    name_cache: ClassVar[dict[Union[int, tuple[int, int]], str]] = {}
    """从context到好友名（备注优先）或群聊名的映射，以及从(context, sender)到群名片的映射。"""

    def __init__(self) -> None:
        self.flows: OrderedDict[
            tuple[int, int], tuple[float, Generator[object, Optional[str], object]]
        ] = OrderedDict()
        """尚在进行的对话流程。

        从(context, sender)到(最后活动时间戳, 程序执行状态)的映射，按最后活动时间从早到晚排序。
        """

    @staticmethod
    def escape(text: str) -> str:
        """CQ码转义。"""
        return (
            text.replace("&", "&amp;")
            .replace("[", "&#91;")
            .replace("]", "&#93;")
            .replace(",", "&#44;")
        )

    @staticmethod
    def gocqhttp(endpoint: str, data: dict = {}, **kwargs) -> dict:
        """向go-cqhttp发送请求，并返回响应数据。

        关于具体参数，必须参考go-cqhttp的API文档。
        https://docs.go-cqhttp.org/api/

        使用例：
        - 发送私聊消息
            gocqhttp("send_private_msg", user_id=114514, message="你好")
        - 获取当前登录账号的昵称
            gocqhttp("get_login_info")["nickname"]
        """
        kwargs.update(data)
        data = requests.post(
            f"http://127.0.0.1:5700/{endpoint}",
            headers={"Content-Type": "application/json"},
            json=kwargs,
        ).json()
        if data["status"] == "failed":
            raise Exception(data["msg"], data["wording"])
        return data["data"] if "data" in data else {}

    @classmethod
    def send(cls, context: int, message: str) -> None:
        """发送消息。

        :param context: 发送目标，正数表示好友，负数表示群。
        :param message: 要发送的消息内容，富文本用CQ码表示。
        """
        cls.gocqhttp(
            "send_msg",
            {"user_id" if context >= 0 else "group_id": abs(context)},
            message=message,
        )

    @staticmethod
    def context_sender_from_gocqhttp_event(data: dict[str, Any]) -> tuple[int, int]:
        """从go-cqhttp的事件数据中提取(context, sender)元组。"""
        sender = int(data["user_id"]) if "user_id" in data else 0
        context = -int(data["group_id"]) if "group_id" in data else sender
        return context, sender

    def gocqhttp_event(self, data: dict[str, Any]) -> bool:
        """接收事件并调用对应的事件处理方法。

        :param data: 来自go-cqhttp的上报数据。
        :returns: True表示事件已受理，不应再交给其他插件；False表示应继续由其他插件处理本事件。
        """
        context, sender = self.context_sender_from_gocqhttp_event(data)
        result: object = None
        # https://docs.go-cqhttp.org/event/
        if data["post_type"] == "message":
            # 这个类型的上报只有好友消息和群聊消息两种。
            message = data["raw_message"]
            # 强制终止超过一天仍未结束的对话流程。
            while (
                self.flows and next(iter(self.flows.values()))[0] < time.time() - 86400
            ):
                self.flows.popitem(last=False)
            # 如果当前上下文中的发送者没有仍在进行的对话流程，有可能因本条消息启动新的对话流程。
            if (context, sender) not in self.flows:
                result = self.on_message(context, sender, message, data["message_id"])
                # 是否启动了新的对话流程？
                if isinstance(result, Generator):
                    self.flows[context, sender] = time.time(), result
                    message = None  # 向Generator首次send的值必须为None
            # 当前上下文中的发送者有无仍在进行（或上面刚启动）的对话流程？
            if (context, sender) in self.flows:
                try:
                    generator = self.flows[context, sender][1]
                    result = generator.send(message)
                    if result:
                        self.flows[context, sender] = time.time(), generator
                        self.flows.move_to_end((context, sender))
                except StopIteration as e:
                    result = e.value
                    del self.flows[context, sender]
        elif data["post_type"] == "request":
            # 这个类型的上报只有申请添加好友和申请加入群聊两种。
            result = self.on_admission(context, sender, data["comment"])
            if result is not None:
                if data["request_type"] == "friend":
                    self.gocqhttp(
                        "set_friend_add_request", flag=data["flag"], approve=result
                    )
                elif data["request_type"] == "group":
                    self.gocqhttp(
                        "set_group_add_request",
                        flag=data["flag"],
                        type=data["sub_type"],
                        approve=result,
                    )
                result = True
        elif data["post_type"] == "meta_event":
            # 这个类型的上报只有心跳，且没有在go-cqhttp的文档中说明。
            result = self.on_interval()
        # 其余所有事件都是通知上报。
        elif data["notice_type"] in ("friend_recall", "group_recall"):
            message = ChatbotBehavior.gocqhttp("get_msg", message_id=data["message_id"])
            message = str(message["raw_message"]) if "raw_message" in message else ""
            result = self.on_message_deleted(
                context, sender, message, data["message_id"]
            )
        elif data["notice_type"] == "offline_file":
            result = self.on_file(
                context,
                sender,
                data["file"]["name"],
                data["file"]["size"],
                data["file"]["url"],
            )
        elif data["notice_type"] == "group_upload":
            url = ChatbotBehavior.gocqhttp(
                "get_group_file_url",
                group_id=-context,
                file_id=data["file"]["id"],
                busid=data["file"]["busid"],
            )["url"]
            result = self.on_file(
                context, sender, data["file"]["name"], data["file"]["size"], url
            )
        if result and context and isinstance(result, str):
            self.send(context, result)
        return bool(result)

    @overload
    def name(self, context: int) -> str:
        """获取好友名（正参数）或群聊名（负参数），备注优先。"""

    @overload
    def name(self, context: tuple[int, int]) -> str:
        ...

    @overload
    def name(self, context: int, sender: int) -> str:
        """获取群名片或用户在群聊中的昵称。"""

    def name(self, context, sender=None) -> str:
        """获取各种用户和群的名称的方法。

        有Python侧一级缓存和go-cqhttp侧二级缓存，因此可以安心频繁调用本方法。
        """
        if sender is not None:
            return self.name((context, sender))
        if context in self.name_cache:
            return self.name_cache[context]
        if isinstance(context, int):
            if context >= 0:
                for response in self.gocqhttp("get_friend_list"):
                    self.name_cache[response["user_id"]] = (
                        response["remark"] or response["nickname"]
                    )
                name = self.name_cache.get(context, "")
            else:
                response = self.gocqhttp("get_group_info", group_id=-context)
                name = response.get("group_memo") or response["group_name"]
        else:
            if context[0] >= 0:
                name = self.name(context[1])
            else:
                response = self.gocqhttp(
                    "get_group_member_info", group_id=-context[0], user_id=context[1]
                )
                name = response.get("card") or response["nickname"]
        self.name_cache[context] = name
        return name

    def on_message(self, context: int, sender: int, text: str, message_id: int):
        """当收到消息时执行此函数。

        如果不知道参数和返回值的含义的话，请看ChatbotBehavior类的说明。
        """

    def on_message_deleted(self, context: int, sender: int, text: str, message_id: int):
        """消息被撤回。"""

    def on_file(self, context: int, sender: int, filename: str, size: int, url: str):
        """接收到离线文件或群有新文件。"""

    def on_admission(self, context: int, sender: int, text: str) -> Optional[bool]:
        """收到了添加好友的请求或加入群聊的请求。

        返回True接受，False拒绝，None无视并留给下一个插件处理。
        """

    def on_interval(self):
        """每隔不到一分钟，此函数就会被调用。

        用于实现定时功能。
        """


class NameCacheUpdater(ChatbotBehavior):
    """与ChatbotBehavior基类联合工作的必备插件。"""
    def gocqhttp_event(self, data: dict[str, Any]) -> bool:
        # 如果有详细的发送者信息，更新名称缓存。
        # 虽然这不应该由每个插件分别运行，但暂时找不到好地方放这个代码，就这样吧。
        context, sender = self.context_sender_from_gocqhttp_event(data)
        if "sender" in data and "group_id" in data:
            self.name_cache[context, sender] = data["sender"].get("card") or data[
                "sender"
            ].get("nickname")
        return False
