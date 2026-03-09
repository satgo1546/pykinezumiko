"""主程序。

plugins目录下的所有模块将自动被视为插件而加载。
"""

import importlib
import pkgutil

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.endpoints import HTTPEndpoint
from starlette.routing import Route

from . import on_event, conf, plugins

for m in pkgutil.iter_modules(plugins.__path__):
    print(f"加载插件 {m.name}")
    importlib.import_module(f"{plugins.__name__}.{m.name}")


class Root(HTTPEndpoint):
    async def get(request: Request) -> Response:
        return PlainTextResponse(f"消息处理端已启动。{request.headers = !r}")

    async def post(request: Request) -> Response:
        on_event(await request.json())
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
