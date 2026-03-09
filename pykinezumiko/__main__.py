import importlib
import pkgutil

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route

from . import Plugin, conf, plugins

for m in pkgutil.iter_modules(plugins.__path__):
    print(f"加载插件 {m.name}")
    importlib.import_module(f"{plugins.__name__}.{m.name}")


async def root(request: Request) -> Response:
    # GET请求来自浏览器。
    if request.method == "GET":
        return PlainTextResponse("消息处理端已启动。")

    # POST请求来自OneBot实现。
    # 为了原路反馈异常信息，在局部变量中记录消息上下文。
    context = 0

    try:
        data = await request.json()
        # 从OneBot事件数据中提取context和sender。
        sender = int(data.get("user_id", 0))
        context = -int(data["group_id"]) if "group_id" in data else sender
        # 易碎的细节：all和any短路求值。
        any(p.on_event(context, sender, data) for p in plugins)
    except Exception as e:
        tb = e.__traceback__
        assert tb
        while tb.tb_next:
            tb = tb.tb_next
        tb = tb.tb_frame
        message = f"来自 {tb.f_code.co_filename}:{tb.f_lineno}:{tb.f_code.co_name} 的 {type(e).__name__}：{e}"
        if context:
            Plugin.send(context, f"执行时发生了下列异常。\n{message}")
        else:
            Plugin.send(conf.BACKSTAGE, f"处理无来源事件时发生了下列异常。\n{message}")
        # 再行抛出错误，以便打印错误堆栈到控制台。
        raise
    return PlainTextResponse("")


uvicorn.Server(
    uvicorn.Config(
        Starlette(
            routes=[
                Route("/", root, methods=["GET", "POST"]),
            ]
        ),
        port=5701,
        log_level="info",
    )
).run()
