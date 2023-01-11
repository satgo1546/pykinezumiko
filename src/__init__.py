import inspect
import time
from collections import OrderedDict
from collections.abc import Generator
from typing import Any, Callable, ClassVar, NoReturn, Optional, Union, overload

import requests

from . import humanity


def bisect_left(a, x, lo, key):
    """为了支持Python 3.9，补一个支持key的二分函数……"""
    hi = len(a)
    while lo < hi:
        mid = (lo + hi) // 2
        if key(a[mid]) < x:
            lo = mid + 1
        else:
            hi = mid
    return lo


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
    为方便计，可以直接返回要回复的文字，与执行send函数无异。
    返回假值（即None、False、""）的场合，表示插件无法处理这个事件。该事件会轮替给下一个插件来处理。
    """

    _name_cache: ClassVar[dict[Union[int, tuple[int, int]], str]] = {}
    """在name方法内部使用的名称缓存。若想在对话中包含某人的名称，请使用name方法。

    从context到好友名或群聊名的映射，以及从(context, sender)到群名片的映射。
    """

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
                result = self.dispatch_command(
                    context, sender, message, data["message_id"]
                )
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
        # 结果是真值的时候，无论是什么类型都要回复出来，除非结果只是True而已。
        # 编写插件时，因为返回了数值等，结果完全不知道为什么什么也没有回复的情况太常发生，于是如此特判。
        if context and result and result is not True:
            self.send(context, format(result))
        return bool(result)

    @overload
    def name(self, context: int, sender: int) -> str:
        """获取各种用户的名称的方法。如果context是群聊，则尝试获取群名片。

        有Python侧一级缓存和go-cqhttp侧二级缓存，因此可以安心频繁调用本方法。
        """

    @overload
    def name(self, context: tuple[int, int]) -> str:
        ...

    @overload
    def name(self, context: int) -> str:
        """获取好友名（正参数）或群聊名（负参数）。

        有Python侧一级缓存和go-cqhttp侧二级缓存，因此可以安心频繁调用本方法。
        """

    def name(self, context, sender=None) -> str:
        if sender is not None:
            return self.name((context, sender))
        if context in self._name_cache:
            return self._name_cache[context]
        if isinstance(context, int):
            if context >= 0:
                for response in self.gocqhttp("get_friend_list"):
                    self._name_cache[response["user_id"]] = response["nickname"]
                name = self._name_cache.get(context, "")
            else:
                response = self.gocqhttp("get_group_info", group_id=-context)
                name = response["group_name"]
        else:
            if context[0] >= 0:
                name = self.name(context[1])
            else:
                response = self.gocqhttp(
                    "get_group_member_info", group_id=-context[0], user_id=context[1]
                )
                name = response.get("card") or response["nickname"]
        self._name_cache[context] = name
        return name

    def dispatch_command(
        self, context: int, sender: int, text: str, message_id: int
    ) -> object:
        """找到并调用某个on_command_×××，抑或是on_message。

        方法名的匹配是模糊的，但要求方法名必须为规范形式。
        具体参照humanity.normalize函数，最重要的是必须是小写。
        由于__getattr__等魔法方法的存在，不可能列出对象支持的方法列表，故当方法名不规范时，无法给出任何警告。

        如果同时定义了on_message、on_command_foo、on_command_foo_bar，最具体的函数会被调用。

        - ".foo bar" → on_command_foo_bar
        - ".foo baz" → on_command_foo
        - ".bar" → on_message

        on_command_×××方法的参数必须支持按参数名传入（关键字参数），且正确标注类型。
        有名为context、sender、text、message_id的参数时，对应的值会被传入。
        """
        parts = humanity.tokenize_command_name(text)
        while parts:
            name = "".join(parts)
            f = getattr(self, "on_command_" + name, None)
            if callable(f):
                return f(
                    **humanity.parse_command(
                        {
                            parameter.name: parameter.annotation
                            for parameter in inspect.signature(f).parameters.values()
                            if parameter.annotation is not parameter.empty
                        },
                        {
                            "context": context,
                            "sender": sender,
                            "text": text,
                            "message_id": message_id,
                        },
                        # 在原始字符串中找到命令名之后的部分。
                        # 证明一下这个二分法数据的单调性？
                        # 平时做算法题怎么都想不到二分答案——而且这除了用来做算法题以外有什么用啊！
                        # 结果真的在实际开发中用到了这种思路，这合理吗？
                        text[
                            bisect_left(
                                range(min(111, len(text))),
                                name,
                                lo=1,
                                key=lambda i: humanity.normalize(text[1:i]),
                            ) :
                        ].strip(),
                    ),
                )
            # 从长到短，一段一段截下，再尝试取用属性。
            parts.pop()
        return self.on_message(context, sender, text, message_id)

    @staticmethod
    def documented(under: Optional[Callable] = None) -> Callable[[Callable], Callable]:
        if under is None:
            under = HelpProvider.on_command_help

        def decorator(f: Callable) -> Callable:
            under.__doc__ = (under.__doc__ or "") + (f.__doc__ or "")
            return f

        return decorator

    def on_message(self, context: int, sender: int, text: str, message_id: int):
        """当收到消息时执行此函数。

        如果不知道参数和返回值的含义的话，请看ChatbotBehavior类的说明。

        因为on_message事件太常用了，扩展了以下方便用法。

        【关于命令自动解析】
        只要定义函数on_command_foo(self, …)，就能处理.foo这样的指令。
        这样一来，只需要处理有格式命令的话，甚至不必编写on_message事件处理器就能做到。
        方法的命名、参数、优先关系等细节请参照dispatch_command方法的文档。
        参数解析的细节请参照humanity.parse_command函数的文档。
        可以在on_command_×××中使用yield（参照下述对话流程功能）。

        【关于对话流程】
        可以像阻塞式控制台程序一样编写事件处理程序，在需要向用户提问的交互式场合非常方便。

            print("你输入的是" + input("请输入文字"))
            → return "你输入的是" + (yield "请输入文字")

        这种写法使用了无法持久化保存的Python生成器，也就是说，进程重启之后程序的执行状态就会消失。
        此外，超过一天没有下文的对话流程会被直接删除。
        """

    def on_message_deleted(self, context: int, sender: int, text: str, message_id: int):
        """消息被撤回。"""

    def on_file(self, context: int, sender: int, filename: str, size: int, url: str):
        """接收到离线文件或群有新文件。"""

    def on_admission(self, context: int, sender: int, text: str) -> Optional[bool]:
        """收到了添加好友的请求或加入群聊的请求。

        返回True接受，False拒绝，None无视并留给下一个插件处理。
        """

    def on_interval(self) -> None:
        """每隔不到一分钟，此函数就会被调用。用于实现定时功能。

        因为空泛地不针对任何人，即使想通过返回值快速回复也不知道会回复到何处。必须通过send方法来发出消息。
        因为插件不应该剥夺其他插件定时处理的能力，所以也不允许返回真值。
        这样一来，这个函数只能返回None了。

        TODO：这里产生的异常信息，还有各种无来源伤害，都应该重定向到体内群。所以要将20commander.py里的INTERIOR常量移动到更大的作用域里
        """


class NameCacheUpdater(ChatbotBehavior):
    """与ChatbotBehavior基类联合工作的必备插件。"""

    def gocqhttp_event(self, data: dict[str, Any]) -> bool:
        # 如果有详细的发送者信息，更新名称缓存。
        context, sender = self.context_sender_from_gocqhttp_event(data)
        if "sender" in data:
            nickname = data["sender"].get("nickname", "")
            self._name_cache[sender] = self._name_cache[sender, sender] = nickname
            self._name_cache[context, sender] = data["sender"].get("card") or nickname
        return False


class HelpProvider(ChatbotBehavior):
    """提供.help命令的插件。@ChatbotBehavior.documented默认将帮助信息置于此处。"""

    def on_command_help(self, x: NoReturn):
        pass
