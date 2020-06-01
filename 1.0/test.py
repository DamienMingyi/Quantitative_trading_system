from threading import Thread
import time
# 进程等待所有线程结束后才会结束

def func():
    print('线程 start')
    time.sleep(10)
    print('线程 end')

if __name__ == '__main__':

    t = Thread(target=func)
    t.start() # 告诉操作系统开一个线程
    print('主')