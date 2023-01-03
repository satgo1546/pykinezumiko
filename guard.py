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
    print(time.ctime())


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    filename='guard.log',
                    filemode='a')
logger = logging.getLogger(__name__)

schedule.every(0.01).minutes.do(checkPullThenPush)
# schedule.every(1).hour.do(a)

while True:
    schedule.run_pending()
    time.sleep(5)
