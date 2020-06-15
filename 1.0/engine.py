"""
Event-driven framework of vn.py framework.
"""

from collections import defaultdict # defaultdict字典当key不存在时返回默认值
from queue import Empty, Queue
# 构造一个FIFO队列，maxsize可以限制队列的大小。如果队列的大小达到了队列的上限，就会加锁，直到队列的内容被消费掉。如果maxsize的值小于等于0，那么队列的尺寸就是无限制的
# empty异常， 只有非阻塞的时候，队列为空，取数据才会报异常
from threading import Thread
from time import sleep
from typing import Any, Callable

EVENT_TIMER = "eTimer"


class Event:
    """
    Event object consists of a type string which is used
    by event engine for distributing event, and a data
    object which contains the real data.
    事件对象由事件引擎用于分发事件的类型字符串和包含实际数据的数据对象组成。
    """

    def __init__(self, type: str, data: Any = None):
        """"""
        self.type = type
        self.data = data


# Defines handler function to be used in event engine.
# 定义要在事件引擎中使用的处理函数
HandlerType = Callable[[Event], None]


class EventEngine:
    """
    Event engine distributes event object based on its type to those handlers registered.
    It also generates timer event by every interval seconds,which can be used for timing purpose.
    事件引擎根据事件对象的类型将其分配给已注册的处理程序。
    它还每隔间隔秒生成一次计时器事件，可用于计时目的。
    """
    # 类的方法或属性前加一个“_”单下划线，意味着该方法或属性不应该去调用
    def __init__(self, interval: int = 1):
        """
        Timer event is generated every 1 second by default, if
        interval not specified.
        """
        self._interval = interval # 间隔秒
        self._queue = Queue() # 事件队列

        self._active = False # 事件引擎开关

        self._thread = Thread(target=self._run) # 创建线程
        self._timer = Thread(target=self._run_timer)

        self._handlers = defaultdict(list) # 创建处理程序字典，key为event.type，元素为list类型
        self._general_handlers = [] # 监听所有类型的处理程序

    def _run(self):
        """
        Get event from queue and then process it.
        从队列中获取事件，然后对其进行处理。
        """
        while self._active:
            try:
                # 从队列里取数据，如果为空的话，blocking = False 直接报 empty异常。如果blocking = True，就是等一会，timeout必须为 0 或正数。None为一直等下去，0为不等，正数n为等待n秒还不能读取，报empty异常
                event = self._queue.get(block=True, timeout=1)
                self._process(event)
                print(self._handlers)
            except Empty:
                pass

    def _process(self, event: Event):
        """
        First ditribute event to those handlers registered listening to this type.
        Then distrubute event to those general handlers which listens to all types.
        首先将事件分发给已注册侦听此类型的处理程序。 然后分发给那些侦听所有类型的常规处理程序。
        """
        if event.type in self._handlers:
            [handler(event) for handler in self._handlers[event.type]]

        if self._general_handlers:
            [handler(event) for handler in self._general_handlers]

    def _run_timer(self):
        """
        Sleep by interval second(s) and then generate a timer event.
        间隔间隔秒睡眠一下，然后生成一个计时器事件。
        """
        while self._active:
            sleep(self._interval)
            event = Event(EVENT_TIMER)
            self.put(event)

    def start(self):
        """
        Start event engine to process events and generate timer events.
        """
        self._active = True
        self._thread.start()
        self._timer.start()

    def stop(self):
        """
        Stop event engine.
        """
        self._active = False
        """
        join所完成的工作就是线程同步，即主线程任务结束之后，进入阻塞状态，一直等待其他的子线程执行结束之后，主线程在终止
        """
        self._timer.join()
        self._thread.join()

    def put(self, event: Event):
        """
        Put an event object into event queue.
        """
        self._queue.put(event)

    def register(self, type: str, handler: HandlerType):
        """
        Register a new handler function for a specific event type.
        Every function can only be registered once for each event type.
        为特定事件类型注册新的处理函数。 对于每种事件类型，每个功能只能注册一次。
        """
        handler_list = self._handlers[type]
        if handler not in handler_list:
            handler_list.append(handler)

    def unregister(self, type: str, handler: HandlerType):
        """
        Unregister an existing handler function from event engine.
        从事件引擎中注销现有的处理函数。
        """
        handler_list = self._handlers[type]

        if handler in handler_list:
            handler_list.remove(handler)

        if not handler_list:
            self._handlers.pop(type)

    def register_general(self, handler: HandlerType):
        """
        Register a new handler function for all event types. Every
        function can only be registered once for each event type.
        """
        if handler not in self._general_handlers:
            self._general_handlers.append(handler)

    def unregister_general(self, handler: HandlerType):
        """
        Unregister an existing general handler function.
        """
        if handler in self._general_handlers:
            self._general_handlers.remove(handler)
