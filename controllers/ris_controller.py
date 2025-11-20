import time
from typing import Dict

from serial import Serial
from loguru import logger as log

from controllers.controller import Controller
from helpers.parameters import Parameters, RisConfigChangeRequest


class RisController(Controller):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ser = None

        port = self._parameters.ris_serial_map[self._component_id]
        log.info(f"[RIS {self._component_id}] Using serial port {port}")

        if not self._test_mode:
            try:
                self.ser = Serial(port, baudrate=115200, timeout=10)
                self.ser.flushInput()
                self.ser.flushOutput()
                log.info(f"[RIS {self._component_id}] Serial connection established.")
            except Exception as e:
                raise RuntimeError(f"Failed to open serial port {port}: {e}")
    
    def _perform_reinit(self) -> None:
        
        if self._test_mode:
            log.info(f"(TEST) [RIS {self._component_id}] Reinit simulated.")
            return
        
        try:
            if self.ser is not None:
                self.ser.flushInput()
                self.ser.flushOutput()
                self.ser.write(b"!RESET\n")
                time.sleep(0.1)
                log.info('[RIS {}] Serial buffers flushed', self._component_id)
        except Exception as e:
            log.error('[RIS {}] Reinit error: {}', self._component_id, e)


    def _on_message_received(self, message: Dict):
        match message['action']:
            
            case 'new-ack':
                self._send_message({'action': 'ready'})
                
            case 'configure':
                config = message['data']
                config = RisConfigChangeRequest(**config)
                self._configure_ris(config)
                self._send_message({'action': 'configure-ack'})
                
            case 'set-pattern':
                config = message['data']
                pattern = config.get("pattern")

                if not isinstance(pattern, str):
                    log.error(f"[RIS {self._component_id}] Invalid pattern format: {pattern}")
                    self._send_message({'action': 'pattern-update', 'data': {'status': 'failure'}})
                    return

                log.debug(f"[RIS {self._component_id}] Setting pattern: {pattern}")

                if self._set_pattern(pattern.encode("utf-8")):
                    log.info(f"[RIS {self._component_id}] Pattern updated successfully.")
                    self._send_message({'action': 'pattern-update', 'data': {'status': 'success'}})
                else:
                    log.error(f"[RIS {self._component_id}] Pattern update failed.")
                    self._send_message({'action': 'pattern-update', 'data': {'status': 'failure'}})

                    
            case 'reinit':
                log.warning('[RIS {}] REINIT requested', self._component_id)
                self._perform_reinit()
                self._send_message({'action' : 'new'})
                
            case 'done':
                log.warning("[RIS] Finish")
                
            case _:
                log.warning(f"[RIS {self._component_id}] Unknown action received.")

    def _configure_ris(self, config: RisConfigChangeRequest):
        log.info(f"SET {config.pattern_index}: {config.pattern_hex}")
        if self._test_mode:
            return

    #        if 'pattern' in config:
        self._pattern = config.pattern_hex
        self._set_pattern(self._pattern.encode("utf-8"))
            
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
            if response.strip() == b"#OK":
                return True
            if time.time() - start_time > 10:
                log.error("RIS: Timeout during pattern setting.")
                return False

        