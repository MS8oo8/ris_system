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

    

# class MockSerial:
#     """Symulowany port szeregowy dla RIS."""
#     def __init__(self, port, baudrate=115200, timeout=10):
#         self.port = port
#         self.baudrate = baudrate
#         self.timeout = timeout
#         self.buffer = []
#         log.info(f"[MockSerial] Połączono z symulowanym portem {port}.")

#     def flushInput(self):
#         self.buffer = []

#     def flushOutput(self):
#         pass

#     def write(self, data):
#         log.info(f"[MockSerial] Odebrano dane do wysłania: {data}")
#         self.buffer.append(data)

#     def readline(self):
#         if self.buffer:
#             return b"#OK\n"  # Symulacja odpowiedzi #OK
#         return b""  # Brak odpowiedzi

class RisController(Controller):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        
        #port = Parameters().get_ris_port(self._component_id) #ok na jednym komputerze to wtedy wiele risow ok
        base_dir = os.path.dirname(os.path.abspath(__file__))
        config_file = os.path.join(base_dir,"config_port/ris_ports.json")
        try:
            with open(config_file, "r") as f:
                ris_port_map = json.load(f)
        except Exception as e:
            raise RuntimeError(f"Can not open file {config_file}: {e}")
        
        port = ris_port_map.get(self._component_id)

        if not port:
            raise RuntimeError(f"No such id for RIS {self._component_id} in {config_file}")
        
        log.info("RIS {} use port {}", self._component_id, port)


        # if self._test_mode:
        #     self.ser = Serial(port, baudrate=115200, timeout=10)
        # else:
        # print("!!!!!!!!!!!!!!!!!!")
        # print(port)
        if not self._test_mode:
            from serial import Serial
            self.ser = Serial(port, baudrate=115200, timeout=10)
            self.ser.flushInput()
            self.ser.flushOutput()
            self.id = id
            self.timeout = 10 #timeout


    def _on_message_received(self, message: Dict):
        match message['action']:
            case 'new-ack':
                # config = message['data']
                # self._configure_ris(config)
                self._send_message({'action': 'ready'})
            case 'configure':
                config = message['data']
                self._configure_ris(config)
                self._send_message({'action': 'configure-ack'})
            case 'set-pattern':
                config = message['data']
                if self._set_pattern(config.get("pattern").encode("utf-8")):
                    self._send_message({'action': 'pattern-update', 'data': {'status' : 'success'}})
                else:
                    self._send_message({'action': 'pattern-update', 'data': {'status' : 'failure'}})
            case _:
                log.warning('this action is not defined!')

    def _configure_ris(self, config: Dict):
        log.info(f"SET {config['index']}: {config['pattern']}")
        if self._test_mode:
            return

        if 'pattern' in config:
            # set or update pattern
            self._pattern = config['pattern']
            self._set_pattern(self._pattern.encode("utf-8"))
            #log.info(f"RIS pattern set to {self._pattern}")
            
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
            # print(response)
            if response.strip() == b"#OK":
                # log.info(f"SET: {pattern}")
                return True
            if time.time() - start_time > 10:
                log.error("RIS: Timeout during pattern setting.")
                return False

        