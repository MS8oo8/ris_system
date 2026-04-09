import time
import glob
from typing import Dict

from serial import Serial
from loguru import logger as log

from controllers.controller import Controller
from helpers.parameters import RisConfigChangeRequest



class RisController(Controller):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ser = None
        log.info(f"[RIS {self._component_id}] Initialized. Waiting for master configuration...")
        
    def _on_message_received(self, message: Dict):
        match message['action']:
            case 'new-ack':
                #self._send_message({'action': 'ready'})
                #pozyskanie parametrów transmisji od głównego kontrolera
                config = message['data']
                port = config['serial_port']
                baudrate = config['baudrate']
                timeout = config['timeout']

                #log.info(f"[RIS {self._component_id}] Received config: Port {port}")

                #zestawienie fizycznego połączenia z panelem RIS
                if not self._test_mode:
                    try:
                        self.ser = Serial(port, baudrate=baudrate, timeout=timeout)
                        self.ser.flushInput()
                        self.ser.flushOutput()
                        log.info(f"[RIS {self._component_id}] Serial connection established!")
                        
                        #jezeli kontroler i panel są poprawnie połączone, mozna wyslac komuniakt ready
                        self._send_message({'action': 'ready'})
                    except Exception as e:
                        #odpowiednik ls /dev/moj_ris - zakładamy ze kod został przystosowany do udev w linux
                        custom_devices = glob.glob('/dev/moj_ris*')
                        log.error(f"[RIS {self._component_id}] Failed to open {port}. Found custom devices: {custom_devices}")
                        #w razie błędu kabla możemy wysłać żądanie restartu
                        self._send_message({
                            'action': 'hardware-error', 
                            'requested_port': port,
                            'found_custom_devices': custom_devices,
                            'error_message': str(e)
                        })
                        
                        self._send_message({'action': 'restart'})
                else:
                    self._send_message({'action': 'ready'})

            case 'configure':
                config = message['data']
                config = RisConfigChangeRequest(**config)
                self._configure_ris(config)
                self._send_message({'action': 'configure-ack'})
            case _:
                log.warning(f"[RIS {self._component_id}] Unknown action received.")

    def _configure_ris(self, config: RisConfigChangeRequest):
        log.info(f"SET {config.pattern_index}: {config.pattern_hex}")
        if self._test_mode:
            return

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
            if time.time() - start_time > self._parameters.ris_serial_timeout:
                log.error("RIS: Timeout during pattern setting.")
                return False
