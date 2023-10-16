import re
import json

import requests

from .. import Plugin

apiKey = "1145141919810HENGHENGAAAAAAAAAAAAAAPIKEY"

def search(imageURL: str, num: int = 1) -> str:
    print("以图搜图", imageURL)
    url = "https://saucenao.com/search.php"

    params = {
        "url": imageURL,
        "db": 999,
        "api_key": apiKey,
        "output_type": 2,
        "numres": num
    }

    r = requests.get(url=url, params=params)
    print("响应", r.text)
    min_ = json.loads(r.text).get("header").get("minimum_similarity")
    res = json.loads(r.text).get("results")
    cnt = 1
    ret = ""
    for j in res:
        if float(j.get("header").get("similarity")) >= min_:
            # 用来防封号的表情符号
            symbol="\x9dface\0id=60\x9c"
            # 对结果中的 ext_urls 插入表情
            if "ext_urls" in j["data"]:
                for index, _ in enumerate(j["data"]["ext_urls"]):
                    j["data"]["ext_urls"][index] = j["data"]["ext_urls"][index].replace(
                        ".", symbol+".")
                    j["data"]["ext_urls"][index] = j["data"]["ext_urls"][index].replace(
                        "://", ":"+symbol+"//")
            # 对结果中的 source 插入表情
            if "source" in j["data"]:
                j["data"]["source"] = j["data"]["source"].replace(
                        ".", symbol+".")
                j["data"]["source"] = j["data"]["source"].replace(
                        "://", ":"+symbol+"//")

            ret += "第"+str(cnt)+"项匹配"+": 相似度"+j.get("header").get("similarity")+"%\n"
            ret += json.dumps(j.get("data"), indent=1)+"\n"
            cnt += 1
    print(f"返回值 {ret!r}")
    return ret

class SauceNAO(Plugin):
    """以图搜图。

    其实只是调用API的产物。
    既然img2img非常火，那么就叫img4img吧，取search for之for之意。
    """

    def on_command_img(self, x: str = ""):
        for i in range(2):
            # 如果用户直接发送了一个图片URL，如.img https://……
            if re.fullmatch(r'https?://\S+', x):
                return search(x)
            # 如果用户在.img后面跟了一个内联图片，即图文混排的消息
            # 或是询问后发送了单张图片
            elif match := re.search(r'\x9dimage\0url=(.*?)\0', x):
                return search(match.group(1))
            # 都没有，且是第一次进入这里（通过.img进入本函数）则询问
            elif not i:
                x = yield "将查找接下来的一张图片。"
            # 第二次（已经询问过了）就寄掉，玩我呢
            else:
                return "没有收到图片。"
