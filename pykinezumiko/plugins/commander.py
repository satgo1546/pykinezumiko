import os
import subprocess
import sys
import time

import pykinezumiko
from pykinezumiko.humanity import format_timespan


class Commander(pykinezumiko.Plugin):
    """提供管理与调试功能的插件。

    如此命名的原因是早期的命令式文件管理器的名字中常常带有“commander”一词。
    """

    def on_command_reload(self):
        print("重启")
        # 提交变更后，先从远程仓库拉取，再推送到远程。
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.email=@",
                "-c",
                "user.name=守护进程",
                "commit",
                "-m",
                "",
                "--allow-empty",
                "--allow-empty-message",
            ],
            check=True,
        )
        subprocess.run(["git", "pull", "--no-rebase", "--no-edit"], check=True)
        subprocess.run(["git", "push"], check=True)
        # 尝试启动新的版本。
        print("启动")
        process = subprocess.Popen([sys.executable, "-m", "pykinezumiko", "通过.reload启动"])
        try:
            print("等待")
            process.wait(5)
        except subprocess.TimeoutExpired:
            # Flask进程启动一段时间内仍在正常运行，表明可以安全地切换到新版。
            print("结束")
            exit()
        else:
            # 新版存在问题。
            print("子进程快速终止")
            return f"Flask进程寄啦（{process.returncode}）！请尽快修复后重新执行.reload。"

    def on_command_debug_s(self, event: pykinezumiko.Event):
        ret = ["下面是调试信息。"]
        ret.append(f"消息发送者 ID = {event.sender}")
        ret.append(f"消息发送者 = {self.bot.name(event.context, event.sender)}")
        ret.append(f"消息上下文 ID = {event.context}")
        ret.append(f"消息上下文 = {self.bot.name(event.context)}")
        if event.context == pykinezumiko.conf.BACKSTAGE:
            ret.append("消息来自管理用群。")
        ret.append("现在 = " + time.strftime("%-Y 年 %-m 月 %-d 日 %H:%M %Z"))
        ret.append(f"所在 = {os.getcwd()}")
        if os.name == "posix":
            with open("/proc/uptime", "r") as f:
                str1 = format_timespan(float(f.readline().split()[0]))
                ret.append(f"服务器运行时间 = {str1}")
            str2 = subprocess.check_output(
                "free --bytes | awk '/Mem/ { print $3 / $2 * 100.0; }'",
                shell=True,
                encoding="iso-8859-1",
            ).strip()
            ret.append(f"内存使用量 = {str2}%")
            str3 = subprocess.check_output(["df", ".", "--output=pcent"]).split()[-1]
            ret.append(f"卷已用空间 = {str3}")
        return "\n".join(ret)

    def on_command_debug_to(self, target: int, content: str):
        self.bot.send(target, content)
        return f"重定向 {content} 到 [{self.bot.name(target)}]。"
