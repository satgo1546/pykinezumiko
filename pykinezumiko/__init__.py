import inspect
import os
import re
import time
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from typing import Any, Callable, ClassVar, Never, TypeVar, overload
import inspect
from collections import defaultdict

import httpx

from . import conf, humanity

CallableT = TypeVar("CallableT", bound=Callable)


def scrub(text: str) -> str:
    r"""删除不应出现在人类产生的文本中的字符。

    会删除除了换行符（"\n"）和制表符（"\t"）以外的所有控制字符和孤代理对。

    因为会删除"\a"，返回的字符串可安全地作为纯文本而不会包含木鼠子码控制序列。
    但是，返回值可能包含"< >"等字符，因此不能直接作为木鼠子码控制序列参数使用。
    """
    return re.sub(r"[\x00-\x08\x0b-x1f\x7f-\x9f\ud800-\udfff]+", text, "")


class Bot:
    def __init__(self):
        self._name_cache: dict[int | tuple[int, int], str] = {}
        """在name方法内部使用的名称缓存。若想在对话中包含某人的名称，请使用name方法。

        从context到好友名或群聊名的映射，以及从(context, sender)到群名片的映射。
        """

    def call(self, endpoint: str, data: dict = {}, **kwargs) -> dict:
        """向OneBot实现发送请求，并返回响应数据。

        使用例：

        - 发送私聊消息

            gocqhttp("send_private_msg", user_id=114514, message="你好")

        - 获取当前登录账号的昵称

            gocqhttp("get_login_info")["nickname"]
        """
        kwargs.update(data)
        data = httpx.post(f"http://127.0.0.1:5700/{endpoint}", json=kwargs).json()
        if data["status"] == "failed":
            raise RuntimeError(data["msg"], data["wording"])
        return data["data"] if "data" in data else {}

    def send(self, context: int, text: str) -> None:
        """发送消息。

        :param context: 发送目标，正数表示好友，负数表示群。
        :param message: 要发送的消息内容，富文本用木鼠子码表示。
        """
        """转换木鼠子码字符串到消息段列表。"""
        segments: list[dict[str, str | dict[str, object]]] = []
        for match in re.finditer(r"[^\a]+|\a<([^<>]*)>", text):
            if args := match.group(1):
                args = args.split(" ")
            match args:
                case None:
                    segments.append({"type": "text", "data": {"text": match.group()}})
                case ["Emoticon", x]:
                    segments.append({"type": "face", "data": {"id": x}})
                case ["Mention", str(x)]:
                    segments.append({"type": "at", "data": {"qq": x}})
                case ["Image", url]:
                    segments.append({"type": "image", "data": {"url": url}})
                case ["Audio", path]:
                    segments = [{"type": "record", "data": {"path": path}}]
                    break
                case ["Video", url]:
                    segments = [{"type": "video", "data": {"url": url}}]
                    break
                case ["File", filename]:
                    name = text[match.end() :] or os.path.basename(filename)
                    if "://" not in filename:
                        filename = os.path.realpath(filename)
                    if context >= 0:
                        self.call("upload_private_file", user_id=context, file=filename, name=name)
                    else:
                        self.call("upload_group_file", group_id=-context, file=filename, name=name)
                    return
                case ["Poke"]:
                    segments = [{"type": "poke", "data": {}}]
                    break
                case ["Special", x]:
                    segments = [{"type": "json", "data": {"data": text[match.end() :]}}]
                    break
                case ["Quote", x]:
                    segments.append({"type": "reply", "data": {"id": x}})
                case ["Begin quote"]:
                    raise NotImplementedError("TODO")
                case _:
                    print("警告：无效的木鼠子码元素", args)
                    segments.append({"type": "face", "data": {"id": "60"}})  # [咖啡]
        self.call("send_msg", {"user_id" if context >= 0 else "group_id": abs(context), "message": segments})

    @overload
    def name(self, context: int, sender: int) -> str:
        """获取各种用户的名称的方法。如果context是群聊，则尝试获取群名片。

        有Python侧一级缓存和go-cqhttp侧二级缓存，因此可以安心频繁调用本方法。
        """

    @overload
    def name(self, context: tuple[int, int]) -> str: ...

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
                for response in self.call("get_friend_list"):
                    self._name_cache[response["user_id"]] = response["nickname"]
                name = self._name_cache.get(context, "")
            else:
                response = self.call("get_group_info", group_id=-context)
                name = response["group_name"]
        else:
            if context[0] >= 0:
                name = self.name(context[1])
            else:
                response = self.call("get_group_member_info", group_id=-context[0], user_id=context[1])
                name = response.get("card") or response["nickname"]
        self._name_cache[context] = name
        return name


@dataclass
class Event:
    context: int
    sender: int
    text: str
    id: int


class Plugin:
    """所有插件的基类。

    继承此类且没有子类的类将自动被视为插件而实例化。
    通过覆盖以“on_”开头的方法，可以监听事件。
    因为这些方法都是空的，不必在覆盖的方法中调用super。
    可以在事件处理中调用self.bot中的方法来作出行动。

    事件包含整数型的context和sender参数。
    正数表示好友，负数表示群。
    context表示消息来自哪个会话。要回复的话请发送到这里。
    sender表示消息的发送者。除了少数无来源的群通知事件，都会是正值。
    例如，私聊的场合，有context == sender > 0；群聊消息则满足context < 0 < sender。

    通常，当插件处理了事件（例如回复了消息），就要返回真值。
    为方便计，可以直接返回要回复的文字，与执行send函数无异。
    返回None的场合，表示插件无法处理这个事件。该事件会轮替给下一个插件来处理。
    """

    def __init__(self, bot: Bot):
        self.bot = bot

    def on_message(self, event: Event):
        """当收到消息时执行此函数。

        如果不知道参数和返回值的含义的话，请看Plugin类的说明。

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

    def on_message_deleted(self, event: Event):
        """消息被撤回。"""

    def on_admission(self, event: Event) -> bool | None:
        """收到了添加好友的请求或加入群聊的请求。

        返回True接受，False拒绝，None无视并留给下一个插件处理。
        """


class Dispatcher:
    def __init__(self, bot: Bot, plugins: list[Plugin]):
        self.bot = bot
        event_handlers = defaultdict[str, list[Callable]]()
        command_handlers = defaultdict[str, list[Callable]]()
        for plugin in plugins:
            for name, handler in inspect.getmembers(plugin, callable):
                if name.startswith("on_command_"):
                    command_handlers[humanity.normalize(name.removeprefix("on_command_"))].append(handler)
                elif name.startswith("on_"):
                    event_handlers[name].append(handler)
        self.event_handlers = dict(event_handlers)
        self.command_handlers = sorted(command_handlers.items())

    def call_handlers(self, handlers: list[Callable], event: Event):
        result: object = None
        for handler in handlers:
            if result := handler():
                break
        # 结果是非空值的时候，无论是什么类型都要回复出来，除非结果只是True而已。
        # 编写插件时，因为意外返回了数值或空字符串等，结果完全不知道为什么什么也没有回复的情况太常发生，于是如此判断。
        if event.context and result is not None:
            self.bot.send(event.context, format(result))

    def on_event(self, data: dict[str, Any]):
        """接收事件并调用对应的事件处理方法。

        :param data: 来自OneBot实现的上报数据。
        """
        # 为了原路反馈异常信息，在局部变量中记录消息上下文。
        context = 0
        try:
            # 从OneBot事件数据中提取context和sender。
            sender = int(data.get("user_id", 0))
            context = -int(data["group_id"]) if "group_id" in data else sender

            result: object = None
            # https://napcat.napneko.icu/onebot/event
            match data:
                case {"post_type": "message", "message": list(message), "message_id": id}:
                    # 这个类型的上报只有好友消息和群聊消息两种。
                    result = self.dispatch_message(context, sender, message, id)
                case {"request_type": ("friend" | "group") as request_type, "comment": message, "flag": flag}:
                    # 这个类型的上报只有申请添加好友和申请加入群聊两种。
                    print("收到申请", data)
                    event = Event(context, sender, scrub(message), 0)
                    for handler in self.event_handlers["on_admission"]:
                        result = handler(event)
                        if result is not None:
                            print("申请处理结果为", result)
                            self.bot.call(
                                "set_friend_add_request" if request_type == "friend" else "set_group_add_request",
                                flag=flag,
                                type=data.get("sub_type"),
                                approve=bool(result),
                            )
                            break
                    else:
                        print("未处理申请")
                case {"notice_type": "friend_recall" | "group_recall"}:
                    message = self.bot.call("get_msg", message_id=data["message_id"])
                    message = str(message.get("message", ""))
                    result = self.call_handlers(
                        self.event_handlers["on_message_deleted"],
                        Event(context, sender, message, data["message_id"]),
                    )
                case {"notice_type": "offline_file", "file": {"name": name, "size": size, "url": url}}:
                    result = self.dispatch_message(context, sender, f"\a<File {url}#size={size}>{name}", 0)
                case {
                    "notice_type": "group_upload",
                    "file": {"name": name, "size": size, "id": id, "busid": busid},
                }:
                    url = self.bot.call("get_group_file_url", group_id=-context, file_id=id, busid=busid)["url"]
                    result = self.dispatch_message(context, sender, f"\a<File {url}#size={size}>{name}", 0)
        except Exception as e:
            tb = e.__traceback__
            assert tb
            while tb.tb_next:
                tb = tb.tb_next
            tb = tb.tb_frame
            message = f"来自 {tb.f_code.co_filename}:{tb.f_lineno}:{tb.f_code.co_name} 的 {type(e).__name__}：{e}"
            if context:
                self.bot.send(context, f"执行时发生了下列异常。\n{message}")
            else:
                self.bot.send(conf.BACKSTAGE, f"处理无来源事件时发生了下列异常。\n{message}")
            # 再行抛出错误，以便打印错误堆栈到控制台。
            raise

    def dispatch_message(self, context: int, sender: int, message: str | list[dict], message_id: int):
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

        if isinstance(message, str):
            text = message
        else:
            r"""转换OneBot消息段列表到木鼠子码字符串。

            木鼠子码用"\a<控制序列 参数值 参数值>"表示。
            通过使用莫名其妙的控制字符，使控制序列与常规文本冲突的可能性降到极低。
            因为"< >"三个字符都被HTML占用，被列为URL中禁止使用的字符，因此参数是网址也没有问题。
            当输入确实包含"\a"时就完蛋了，到那时再自求多福吧。

            木鼠子码最大的好处是，将数据结构统一展平成字符串后，能在整条消息上使用正则表达式，
            而且不太需要特别处理就能正确应对表情等元素。
            OneBot协议定义的元素名满是中式英语，参数也不统一，因此不得不花费很多代码来转换。
            "\a"是Python中为数不多的有单字母缩写且不属于正则表达式空白（r"\s"）的控制字符之一。
            """
            text = ""
            for segment in message:
                # https://napcat.napneko.icu/onebot/sement
                match segment:
                    case {"type": "text", "data": {"text": str(x)}}:
                        text += x
                    case {"type": "face", "data": {"id": x}}:
                        text += f"\a<Emoticon {x}>"
                    case {"type": "at", "data": {"qq": x}}:
                        text += f"\a<Mention {x}>"  # 包含Mention all
                    case {"type": "image", "data": {"url": url}}:
                        text += f"\a<Image {url}>"
                    case {"type": "record", "data": {"path": path}}:
                        text += f"\a<Audio {path}>"
                    case {"type": "video", "data": {"url": url}}:
                        text += f"\a<Video {url}>"
                    case {"type": "file", "data": {"file_id": x}}:
                        text += f"\a<File {x}>"
                    case {"type": "poke"} as a:
                        print("POKE还有其他属性吗？", a)
                        text += "\a<Poke>"
                    case {"type": "json", "data": {"data": x}}:
                        text += f"\a<Special>{x}"
                    case {"type": "reply", "data": {"id": x}}:
                        text = f"\a<Quote {x}>" + text
                    case {"type": "forward", "data": {"content": x}}:
                        print("收到合并转发", x)
                        text += "\a<Begin quote>"
                    case {"type": x, "data": data}:
                        print("警告：未知的消息元素，data字段 =", data)
                        text += f"\a<{x}>"
        text = scrub(text)
        if match := re.match(r"[.。!！]", text):
            command = humanity.normalize(text[match.end() :])
            index = bisect_left(self.command_handlers, (command, []))
            if index < len(self.command_handlers):
                command_name, handlers = self.command_handlers[index]
                if command.startswith(command_name):
                    # 在原始字符串中二分找到命令名之后的部分。
                    index = (
                        bisect_right(
                            range(len(text) + 1),
                            command_name,
                            lo=match.end(),
                            key=lambda i: humanity.normalize(text[match.end() : i]),
                        )
                        - 1
                    )
                    assert index >= match.end(), "析出长度为负的命令名"
                    assert humanity.normalize(text[match.end() : index]), "析出的命令名不是析出的命令名"
                    self.call_handlers(handlers, Event(context, sender, text[index:], message_id))
                    return
                # except humanity.CommandSyntaxError as e:
                # return e.args[0] if e.args else inspect.getdoc(f)
                # return f(**kwargs)
        self.call_handlers(self.event_handlers["on_message"], Event(context, sender, text, message_id))


class NameCacheUpdater(Plugin):
    """与Plugin基类联合工作的必备插件。"""

    def on_event(self, context: int, sender: int, data: dict[str, Any]) -> bool:
        # 如果有详细的发送者信息，更新名称缓存。
        if "sender" in data:
            nickname = data["sender"].get("nickname", "")
            self.bot._name_cache[sender] = self.bot._name_cache[sender, sender] = nickname
            self.bot._name_cache[context, sender] = data["sender"].get("card") or nickname
        return False


class Logger(Plugin):
    """调试用，在控制台中输出消息的内部表示。"""

    def on_message(self, event: Event):
        print(repr(event))


class HelpProvider(Plugin):
    """提供.help命令的插件。@Plugin.documented默认将帮助信息置于此处。"""

    def on_command_help(self, _: Never):
        pass


def documented(
    under: Callable | None = HelpProvider.on_command_help,
) -> Callable[[CallableT], CallableT]:
    """使用此装饰器添加单条命令帮助的第一行到帮助索引命令中。

    要添加到总目录.help中：

        @pykinezumiko.documented()
        def on_command_foo(self):
            ...

    要作为子命令添加到某一其他命令的帮助中：

        @pykinezumiko.documented(on_command_foo)
        def on_command_foo_bar(self):
            ...
    """

    def decorator(f: CallableT) -> CallableT:
        under.__doc__ = (
            (inspect.getdoc(under) or "")
            + "\n‣ "
            + (f.__doc__ or humanity.command_prefix[0] + f.__name__.removeprefix("on_command_"))
            .partition("\n")[0]
            .strip()
        )
        return f

    return decorator
