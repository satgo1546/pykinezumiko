import os
import time
import schedule
import subprocess

def checkPullThenPush():
    if subprocess.check_output("git pull", shell=True)==b'Already up to date.\n':
        os.system("git add .")
        os.system("git commit -m 'schedule at:"+time.ctime()+"'")
        os.system("git push")
    print(time.ctime())

schedule.every(0.01).minutes.do(checkPullThenPush)
#schedule.every(1).hour.do(a)

while True:
    schedule.run_pending()
    time.sleep(5)