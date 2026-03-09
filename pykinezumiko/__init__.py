"""与OneBot实现交互的模块。

通过以“on_”开头的函数装饰器，可以监听事件。
可以在事件处理中调用本模块的函数来作出行动。
为方便计，可以直接返回要回复的文字，与执行send函数无异。
"""

from collections import defaultdict

import inspect
import os
import re
import time
from bisect import bisect_left
from dataclasses import dataclass
from typing import Any, Callable, ClassVar, Never, TypeVar, overload

import httpx

from . import conf, humanity

CallableT = TypeVar("CallableT", bound=Callable)


def segments_to_str(message: list[object]) -> str:
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
            case {"type": "text", "data": {"text": x}}:
                assert isinstance(x, str)
                text += x.replace("\a", "")
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
    return text


def str_to_segments(text: str) -> list[dict[str, str | dict[str, object]]]:
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
            case ["File", x]:
                segments = [{"type": "file", "data": {"file_id": x}}]
                break
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
    return segments


def onebot(endpoint: str, data: dict = {}, **kwargs) -> dict[str, Any]:
    """向OneBot实现发送请求，并返回响应数据。

    使用例：

    - 发送私聊消息

        onebot("send_private_msg", user_id=114514, message="你好")

    - 获取当前登录账号的昵称

        onebot("get_login_info")["nickname"]
    """
    kwargs.update(data)
    data = httpx.post(f"http://127.0.0.1:5700/{endpoint}", json=kwargs).json()
    if data["status"] == "failed":
        raise RuntimeError(data["msg"], data["wording"])
    return data["data"] if "data" in data else {}


def send(context: Entity | int, message: str) -> None:
    """发送消息。

    :param context: 发送目标，正数表示好友，负数表示群。
    :param message: 要发送的消息内容，富文本用木鼠子码表示。
    """
    if isinstance(context, Entity):
        context = context.id
    onebot(
        "send_msg",
        {"user_id" if context >= 0 else "group_id": abs(context)},
        message=str_to_segments(message),
    )


def send_file(context: int, filename: str, name: str | None = None) -> None:
    """发送文件。

    :param context: 发送目标。
    :param filename: 本机文件路径。
    :param name: 发送时显示的文件名。默认为路径中指定的文件名。
    """
    name = name or os.path.basename(filename)
    filename = os.path.realpath(filename)
    if context >= 0:
        onebot("upload_private_file", user_id=context, file=filename, name=name)
    else:
        onebot("upload_group_file", group_id=-context, file=filename, name=name)


def _call_handlers(handlers: list[EventHandlerT], event: Event):
    results = []
    exceptions = []
    for handler in handlers:
        try:
            result = handler(event)
        except Exception as e:
            exceptions.append(e)
            continue
        # 结果是非空值的时候，无论是什么类型都要回复出来，除非结果只是True而已。
        # 编写插件时，因为意外返回了数值或空字符串等，结果完全不知道为什么什么也没有回复的情况太常发生，于是如此判断。
        if result is not None:
            results.append(format(result))
    if exceptions:
        raise ExceptionGroup("事件处理函数出错", exceptions)
    else:
        send(event.context, "\n".join(results))


def on_event(data: dict[str, Any]) -> bool:
    """接收事件并调用对应的事件处理函数。

    :param data: 来自go-cqhttp的上报数据。
    :returns: True表示事件已受理，不应再交给其他插件；False表示应继续由其他插件处理本事件。
    """
    result: object = None
    # https://napcat.napneko.icu/onebot/event

    # 为了原路反馈异常信息，在局部变量中记录消息上下文。
    # 从OneBot事件数据中提取context和sender。
    if sender := data.get("sender"):
        sender = Entity(int(sender.get("user_id", "0")), str(sender.get("card", sender.get("nickname", ""))))
    else:
        sender = Entity(int(data.get("user_id", "0")), "")
    if context := 0:
        context = sender
    else:
        context = -int(data["group_id"]) if "group_id" in data else sender
    try:
        match data:
            case {"post_type": "message", "message": list(x), "message_id": id}:
                # 这个类型的上报只有好友消息和群聊消息两种。
                result = _call_handlers(_on_message_handlers, Event(context, sender, segments_to_str(x), id))
            case {"post_type": "request", "comment": message}:
                # 这个类型的上报只有申请添加好友和申请加入群聊两种。
                result = on_admission(context, sender, message)
                if result is not None:
                    if data["request_type"] == "friend":
                        onebot("set_friend_add_request", flag=data["flag"], approve=result)
                    elif data["request_type"] == "group":
                        onebot("set_group_add_request", flag=data["flag"], type=data["sub_type"], approve=result)
                    result = True
            case {"notice_type": "friend_recall" | "group_recall", "message_id": id}:
                message = onebot("get_msg", message_id=id)
                message = str(message["raw_message"]) if "raw_message" in message else ""
                result = on_message_deleted(context, sender, message, id)
            case {"notice_type": "offline_file", "file": {"name": name, "size": size, "url": url}}:
                result = on_file(context, sender, data["file"]["name"], data["file"]["size"], data["file"]["url"])
            case {"notice_type": "group_upload", "file": {"id": id, "busid": busid}}:
                url = onebot("get_group_file_url", group_id=-context, file_id=id, busid=busid)["url"]
                result = on_file(context, sender, data["file"]["name"], data["file"]["size"], url)
        return result is not None
    except Exception as e:
        tb = e.__traceback__
        assert tb
        while tb.tb_next:
            tb = tb.tb_next
        tb = tb.tb_frame
        message = f"来自 {tb.f_code.co_filename}:{tb.f_lineno}:{tb.f_code.co_name} 的 {type(e).__name__}：{e}"
        if context:
            send(context, f"执行时发生了下列异常。\n{message}")
        else:
            send(conf.BACKSTAGE, f"处理无来源事件时发生了下列异常。\n{message}")
        # 再行抛出错误，以便打印错误堆栈到控制台。
        raise


def on_admission(context: int, sender: int, text: str) -> bool | None:
    """收到了添加好友的请求或加入群聊的请求。

    返回True接受，False拒绝，None无视并留给下一个插件处理。
    """


@dataclass
class Entity:
    id: int
    name: str

    def __index__(self) -> int:
        return self.id

    def __format__(self, format_spec: str, /) -> str:
        return format(self.name, format_spec)


@dataclass
class Event:
    """事件包含整数型的context和sender参数。
    正数表示好友，负数表示群。
    context表示消息来自哪个会话。要回复的话请发送到这里。
    sender表示消息的发送者。除了少数无来源的群通知事件，都会是正值。
    例如，私聊的场合，有context == sender > 0；群聊消息则满足context < 0 < sender。
    """

    context: Entity
    sender: Entity
    text: str
    message_id: int


EventHandlerT = TypeVar("EventHandlerT", bound=Callable[[Event], str | None])

_on_command_handlers = defaultdict(list)


def on_command(name: str) -> Callable[[EventHandlerT], EventHandlerT]:
    """用装饰器@on_command("foo")来监听.foo这样的指令。
    这样一来，只需要处理有格式命令的话，甚至不必编写on_message事件处理器就能做到。
    """

    def decorator(f: EventHandlerT) -> EventHandlerT:
        _on_command_handlers[name].append(f)
        return f

    return decorator


_on_message_handlers = []


def on_message(f: EventHandlerT) -> EventHandlerT:
    """当收到消息时执行此函数。"""
    _on_message_handlers.append(f)
    return f


@on_message
def _(event: Event):
    """调试用，在控制台中输出消息的内部表示。"""
    print(repr(event))


@on_command("help")
def _on_command_help(event: Event):
    """提供.help命令的插件。@Plugin.documented默认将帮助信息置于此处。"""
    pass


def documented(under: Callable | None = _on_command_help) -> Callable[[CallableT], CallableT]:
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
