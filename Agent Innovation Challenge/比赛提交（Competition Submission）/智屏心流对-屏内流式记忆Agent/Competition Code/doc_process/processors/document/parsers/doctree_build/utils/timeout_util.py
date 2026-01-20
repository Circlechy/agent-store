# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
"""Module providing a timeout tool."""
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import time
from functools import wraps
from threading import Thread

from doc_process.utils.error_code import ProcessorException, ErrorCode

DEFAULT_TIMEOUT = 60


class ThreadWithReturnValue(Thread):
    """ Thread with return value """

    def __init__(self, func, *args, **kwargs):
        super(ThreadWithReturnValue, self).__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.result = None

    def run(self):
        self.result = self.func(*self.args, **self.kwargs)

    def get_result(self):
        """ get result of thread """
        return self.result


def timeout(seconds=None):
    """Add a timeout parameter to a function and return it.

    :param seconds: optional time limit in seconds or fractions of a second. If None is passed, no timeout is applied.
        This adds some flexibility to the usage: you can disable timing out depending on the settings.
    :type seconds: float

    :raises: TimeoutError if time limit is reached

    It is illegal to pass anything other than a function as the first
    parameter. The function is wrapped and returned to the caller.
    """

    def decorate(function):
        @wraps(function)
        def new_function(*args, **kwargs):
            timeout_wrapper = _Timeout(function, seconds or kwargs.get("timeout_decorator_seconds", DEFAULT_TIMEOUT))
            return timeout_wrapper(*args, **kwargs)

        return new_function

    return decorate


class _Timeout(object):
    """ class for function timeout decorator """

    def __init__(self, function, limit):
        """Initialize instance in preparation for being called."""
        self.__limit = limit
        self.__function = function
        self.__name__ = function.__name__
        self.__doc__ = function.__doc__
        self.__timeout = time.time()

    def __call__(self, *args, **kwargs):
        thread = ThreadWithReturnValue(self.__function, *args, **kwargs)
        thread.daemon = True
        thread.start()
        while time.time() < self.__limit + self.__timeout:
            if thread.is_alive():
                time.sleep(0.01)
                continue
            return thread.get_result()
        raise ProcessorException(ErrorCode.TIMEOUT,
                                 "Time out (> {} seconds) in function '{}'".format(self.__limit, self.__name__))
