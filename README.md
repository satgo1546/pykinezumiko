# 木鼠子 ⅱ Python Ver. ~ 木卫二 ~

```
         _,met$$$$$gg.           pi@raspberrypi
      ,g$$$$$$$$$$$$$$$P.        OS: Debian 11 bullseye
    ,g$$P""       """Y$$.".      Kernel: aarch64 Linux 5.15.61-v8+
   ,$$P'              `$$$.      Uptime: 6d 12h 2m
  ',$$P       ,ggs.     `$$b:    Packages: 597
  `d$$'     ,$P"'   .    $$$     Shell: bash 5.1.4
   $$P      d$'     ,    $$P     Resolution: No X Server
   $$:      $$.   -    ,d$$'     WM: Not Found
   $$\;      Y$b._   _,d$P'      Disk: 1.9G / 30G (7%)
   Y$$.    `.`"Y$$$$P"'          CPU: BCM2835 @ 4x 1.8GHz
   `$$b      "-.__               RAM: 251MiB / 7812MiB
    `Y$$
     `Y$$.
       `$$b.
         `Y$$b.
            `"Y$b._
                `""""
```

这里是今天也在树莓派4B上被修出新bug的骰娘木鼠子。

## 技术信息

架构仍是经典的双端分离：go-cqhttp负责假装自己是QQ，Flask + requests这边负责消息的实际处理。这回因为是CQHTTP，所以两边用HTTP和JSON通信。具体来说，就是像下面这样。

```
┌────────────────────────┐POST ┌────────────────────────┐
│ go-cqhttp              ├────►│ Flask                  │
│ http://localhost:5700/ │◄────┤ http://localhost:5701/ │
└────────────────────────┘ POST└────────────────────────┘
```

端口号是go-cqhttp自动生成的配置文件中的默认值，现在写死了，改的话要改好几个地方。go-cqhttp收到消息时，会发送请求给Flask端。Flask端想要发出消息时，会调用requests库向go-cqhttp发出请求。这是标准的go-cqhttp通信流程。

要部署的话，首先要获取[go-cqhttp](https://docs.go-cqhttp.org/)的二进制发行版，放在任意位置运行，在生成配置文件时选择使用HTTP通信。在配置中请确认下列信息：

- 账号和密码
- 心跳间隔置为数秒～一分钟（被当作方便的定时器来用了）
- 数据库处于启用状态（这应该是默认值）
- 反向HTTP POST列表中包含`http://127.0.0.1:5701/`一项（这应该是一条模板配置，解除注释即可）

额外需要的材料列表如下：

- 至少3.9条巨蟒和它们的
    - 烧瓶
    - 枕头
    - 请求书
    - 四维超立方体

```sh
sudo apt-get install python3-flask python3-pil python3-requests python3-tesserocr git
sudo apt-get install \
  tesseract-ocr-chi-sim-vert \
  tesseract-ocr-chi-tra-vert \
  tesseract-ocr-jpn \
  tesseract-ocr-jpn-vert \
  tesseract-ocr-script-hans \
  tesseract-ocr-script-hans-vert \
  tesseract-ocr-script-hant \
  tesseract-ocr-script-hant-vert \
  tesseract-ocr-script-jpan \
  tesseract-ocr-script-jpan-vert \
  tesseract-ocr-script-latn # 语言文件备用，具体要哪些我也不太清楚。硬盘空间大就是阔气
```

还需要在conf.py中配置少量紧急情况也需要使用的信息。

运行方法是在两个窗口分别启动go-cqhttp（`./go-cqhttp`）和消息处理端（`python -m pykinezumiko`）。使用Raspbian自带的Python即可，无需创建虚拟环境等。因为重启go-cqhttp需要重新发送登录信息，甚至重新扫码（`session.token`失效的场合），所以尽量少重启go-cqhttp。

消息处理端服务器启动时不断尝试监听目标端口，因此可以同时打开两个消息处理程序，甲成功监听的话，乙就会因端口被占用而被挡在门外。甲挂掉后，乙自然接管。这便是自我更新的原理：执行git pull之后，启动新的消息处理程序，再退出自己。

> 木鼠子——在生产环境使用调试模式实现重要特性的先驱者

这次采用了模块化的结构，插件直接放置在pykinezumiko/plugins文件夹下。除了阅读ChatbotBehavior类的文档，还可以跟随典例从实践中学习插件的制作方法。

## 以下功能在梦里有

因为在x86-64电脑上没法运行ARM64的程序，即使替换成x86-64版本的程序来尝试运行也势必会把树莓派上正在工作的踢下线，所以有个办法不需要真的登录QQ也能运行起一部分代码。单纯运行`python -m pykinezumiko`的话，只会启动Flask端。用浏览器访问`http://localhost:5701/`，因为检测到是来自浏览器的GET而非来自go-cqhttp的POST，就会提供一个假的聊天窗口。因为是假的聊天窗口，所以很多功能都用不了，只适合用来测试聊天AI，与QQ绑定的逻辑还是要传到树莓派上实机测试。

### clock todos

- [ ] 取消机能
- [ ] 周天小时分钟秒
- [ ] 顺序变换
- [ ] 加减乘除

鼠：一直很想要但没做的功能

- [ ] 直接指定绝对时间，比如.clock 2023-01-09 刷红票
- [ ] .clock 明天 blabla
- [ ] .clock 明天8:00 刷红票
