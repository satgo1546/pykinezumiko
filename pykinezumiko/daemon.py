import logging
import subprocess
import sys
import time
from typing import NoReturn

import requests

from . import conf


def checkPullThenPush() -> None:
    logger.info("checkPullThenPush()")
    logger.info("%s", subprocess.check_output(["git", "add", "."]))
    logger.info(
        "%s",
        subprocess.check_output(
            [
                "git",
                "-c",
                "user.email=@",
                "-c",
                "user.name=守护进程",
                "commit",
                "-m",
                f"schedule at:{time.ctime()}",
            ]
        ),
    )
    logger.info(
        "%s",
        subprocess.check_output(
            ["git", "pull", "--no-rebase", "--no-edit", "origin", "main"]
        ),
    )
    logger.info("%s", subprocess.check_output(["git", "push"]))


def pullIsAlreadyUpToDate() -> bool:
    logger.info("pullIsAlreadyUpToDate()")
    output = subprocess.check_output(
        ["git", "pull", "--no-rebase", "--no-edit", "origin", "main"],
        encoding="iso-8859-1",
    )
    logger.info("%s", output)
    return "Already up to date" in output


def report(text: object) -> None:
    try:
        requests.get(
            f"http://127.0.0.1:5700/send_msg",
            {
                "group_id" if conf.INTERIOR < 0 else "user_id": abs(conf.INTERIOR),
                "message": f"\U0001f608 {text}",
            },
        )
    except requests.exceptions.RequestException:
        print(f"汇报消息失败 {text}")


def main() -> NoReturn:
    process = None
    start_time = time.strftime("%c %z")
    restart_count = 0
    while True:
        # process为空 = 第一轮循环：启动Flask
        # returncode不为空 = 上一轮循环时Flask寄了：重启Flask
        if process is None or process.returncode is not None:
            restart_count += 1
            message = "通过守护脚本启动"
            if process and process.returncode is not None:
                message = f"自 {start_time} 以来第 {restart_count} 回重新启动进程"
                if process.returncode:
                    message += f"，上回进程异常退出代码 {process.returncode}"
            process = subprocess.Popen([sys.executable, "-m", "pykinezumiko", message])
        try:
            if process.wait(7777):
                print("Flask进程异常退出，等待仓库更新")
                report(f"Flask进程寄啦！（{process.returncode}）")
                # 迫真慢启动……
                time.sleep(7)
                if pullIsAlreadyUpToDate():
                    time.sleep(77)
                    if pullIsAlreadyUpToDate():
                        time.sleep(77)
                        if pullIsAlreadyUpToDate():
                            time.sleep(77)
                            if pullIsAlreadyUpToDate():
                                time.sleep(777)
                                while pullIsAlreadyUpToDate():
                                    time.sleep(7777)
            else:
                print("Flask进程正常退出，同步并重启")
                checkPullThenPush()
                report("Flask进程正常退出，已完成同步，即将重启。")
        except subprocess.TimeoutExpired:
            # Flask进程仍在正常运行
            checkPullThenPush()
        except:
            # 发生了异常
            logger.error("发生了异常！", exc_info=True)


if __name__ == "__main__":
    # logging config
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.DEBUG,
        filename="daemon.log",
        filemode="a",
    )
    logger = logging.getLogger(__name__)
    main()
