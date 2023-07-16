import errno
import time
from http.server import ThreadingHTTPServer
from werkzeug.serving import WSGIRequestHandler, get_sockaddr, select_address_family

from .app import app

class PerseveringWSGIServer(ThreadingHTTPServer):
    """持续不断地尝试监听端口的多线程服务器。

    werkzeug.serving.make_server创建的服务器只是为了打印自定义错误信息
    “Either identify and stop that program, or start the server with a different …”
    就把OSError据为己有，所以不得不自己定义一个服务器类来使用。
    """
    multithread = True
    multiprocess = False

    def __init__(self, host: str, port: int, app) -> None:
        handler = WSGIRequestHandler
        handler.protocol_version = "HTTP/1.1"

        self.host = host
        self.port = port
        self.app = app
        self.address_family = address_family = select_address_family(host, port)
        self.ssl_context = None

        super().__init__(
            get_sockaddr(host, port, address_family),  # type: ignore[arg-type]
            handler,
            bind_and_activate=False,
        )
        while True:
            try:
                self.server_bind()
                self.server_activate()
            except OSError as e:
                if e.errno == errno.EADDRINUSE:
                    print("端口被占用，将重试")
                    time.sleep(1)
                else:
                    raise
            else:
                break


PerseveringWSGIServer("127.0.0.1", 5701, app).serve_forever()
