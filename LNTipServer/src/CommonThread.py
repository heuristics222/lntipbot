import abc
from datetime import datetime
import logging
from threading import Thread, Condition
import traceback

class CommonThread(Thread):
    def __init__(self, threadName, loggerName):
        super().__init__(name=threadName)
        self.logger = logging.getLogger(name=loggerName)
        self.isShutdown = False
        self.cond = Condition()

    def start(self):
        super().start()
        return self

    def shutdown(self):
        self.logger.info(f'{self.getName()} shutting down...')
        self.isShutdown = True
        with self.cond:
            self.cond.notify()

    @abc.abstractmethod
    def tryRun(self):
        return

    @abc.abstractmethod
    def handleError(self, e):
        return

    @abc.abstractmethod
    def handleFinally(self):
        return

    def printErrorInfo(self, e):
        self.logger.error(f'Error type: {type(e)}')
        self.logger.info(f'{e}\n\n{traceback.format_exc()}')

    def throttle(self):
        if not self.throttled:
            self.throttled = True
            t = datetime.utcnow()
            sleeptime = 60 - (t.second + t.microsecond/1000000.0)
            with self.cond:
                self.cond.wait(sleeptime)

    def run(self):
        self.logger.info('Starting thread...')

        while not self.isShutdown:
            try:
                self.throttled = False
                self.tryRun()
            except Exception as e:
                try:
                    self.printErrorInfo(e)
                    self.handleError(e)
                except Exception as e2:
                    self.logger.info('Error caught from handleError')
                    self.printErrorInfo(e2)
                # In case of error, throttle the thread
                self.throttle()
            finally:
                try:
                    self.handleFinally()
                except Exception as e:
                    self.logger.info('Error caught from handleFinally')
                    self.printErrorInfo(e)
        
        self.logger.info(f'Thread exited...')