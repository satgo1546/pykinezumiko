import time
import logging
import schedule
import subprocess


def checkPullThenPush():
    logger.info(subprocess.getoutput("git pull"))
    logger.info(subprocess.getoutput("git add ."))
    logger.info(subprocess.getoutput(
        "git commit -m 'schedule at:"+time.ctime()+"'"))
    logger.info(subprocess.getoutput("git push"))
    # 重启flask


# schedules
schedule.every(1).second.do(checkPullThenPush)
#schedule.every(1).hour.do(checkPullThenPush)

# logging config
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    level=logging.DEBUG,
                    filename="guard.log",
                    filemode="a")
logger = logging.getLogger(__name__)

while True:
    schedule.run_pending()
    time.sleep(5)
