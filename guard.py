import os
import time
import schedule

#TODO   git add .
#       git commit ''
#       git push

#TODO   git pull

def a():
    os.system("git add .")
    os.system("git commit 'schedule at:"+time.ctime()+"'")
    os.system("git pull")
    print(time.ctime())

schedule.every(0.01).minutes.do(a)
#schedule.every(1).hour.do(a)

while True:
    schedule.run_pending()
    time.sleep(10)