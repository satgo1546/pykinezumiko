"""主程序。

会自动加载plugins目录下的所有模块。
"""

import importlib
import pkgutil

import uvicorn
from starlette.applications import Starlette
from starlette.endpoints import HTTPEndpoint
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route

from . import Bot, Dispatcher, Plugin
from . import plugins as plugins_module

bot = Bot()

for p in sorted(m.name for m in pkgutil.iter_modules(plugins_module.__path__)):
    print(f"加载插件模块 {p}")
    importlib.import_module(f"{plugins_module.__name__}.{p}")


# 虽然只是加载而没有将模块留下，但是其中的类皆已成功定义。
# 靠深度优先搜索找出所有继承了Plugin但没有子类的类，它们是要实例化的插件类。
def leaf_subclasses(cls: type) -> list[type]:
    """找出指定类的所有叶子类。"""
    return [s for c in cls.__subclasses__() for s in leaf_subclasses(c)] or [cls]


plugins: list[Plugin] = []
for p in leaf_subclasses(Plugin):
    print(f"加载插件类 {p.__name__}")
    plugins.append(p(bot))

# 上述过程中易碎的细节：
# • 插件模块相互独立，从而按导入顺序加载。
# • Python 3.4起，__subclasses__按字典键的顺序返回子类列表。
# • Python 3.6起，字典按加入顺序迭代键。
# • Python 3.9起，文档明确指出__subclasses__按子类定义先后顺序返回子类列表。
# • leaf_subclasses函数返回列表从而保持顺序。

dispatcher = Dispatcher(bot, plugins)


class Root(HTTPEndpoint):
    async def get(request: Request) -> Response:
        return PlainTextResponse(f"消息处理端已启动。{request.headers = !r}")

    async def post(request: Request) -> Response:
        dispatcher.on_event(await request.json())
        return PlainTextResponse("")


uvicorn.Server(
    uvicorn.Config(
        Starlette(
            routes=[
                Route("/", Root),
            ]
        ),
        port=5701,
        log_level="info",
    )
).run()
