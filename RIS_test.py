import zmq
from loguru import logger as log
# import time
import json
# from RsSmw import *
import numpy as np
from typing import Dict, Callable
from helpers.zmq_connection import ZmqClient
from controllers.controller import Controller
from unittest.mock import Mock
from helpers.parameters import Parameters
import time
import os
#if self._test_mode:
    #from serial import Serial
#else:
#Serial = Mock()
from serial import Serial

def _set_pattern(self, pattern: str) -> bool:
    if not pattern:
        log.error("Invalid pattern received")
        return False
    
    self.ser.flushInput()
    self.ser.flushOutput()
    self.ser.write(b"!" + pattern + b"\n")
    start_time = time.time()
    while True:
        response = self.ser.readline()
        print(response)
        if response.strip() == b"#OK":
            log.info(f"RIS: Pattern {pattern} successfully set.")
            return True
        if time.time() - start_time > 10:
            log.error("RIS: Timeout during pattern setting.")
            return False


