from typing import Dict, List

import subprocess
import numpy as np
from loguru import logger as log

from controllers.controller import Controller
from helpers.parameters import RxConfigChangeRequest

usrp = None 


class RxController(Controller):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
        self._avg_power_history = self._parameters.rx_initial_avg_power_history_dbm
        self._log_history_coeff = self._parameters.rx_log_history_coeff

        self._frequency = None
        self._samp_rate = None
        self._rx_gain = None
        self._buffer_size = None 
        self._N = None 
        self._usrp_usb_sn = None

        self._consecutive_failures = 0 

        """
        if self._test_mode:
            log.info(f"(test mode) Simulating USRP connection for RX {self._component_id}")
        else:
            import uhd
            global usrp

            try:
                usrp = uhd.usrp.MultiUSRP(f'serial={self._parameters.rx_usrp_serial_map[self._component_id]}')
                log.info(f"[RX {self._component_id}] Connected to USRP.")
            except KeyError:
                log.error(f"No USRP serial number found in parameters for RX ID '{self._component_id}'")
            except Exception as ex:
                # self._list_available_usrp_serials()
                log.error(f"[RX {self._component_id}] Failed to initialize USRP: {ex}")
                
        """

        log.info(f"[RX {self._component_id}] Initialized. Waiting for master configuration...")
        

    def _recv_samples_safe(self) -> np.ndarray:
        global usrp
        assert self._test_mode == False, 'Cannot receive samples in test mode.'
        
        try:
            samples = usrp.recv_num_samps(
                self._buffer_size,
                self._frequency,
                self._samp_rate,
                [0],
                self._rx_gain
            )

            return samples
        except Exception as e:
            msg = str(e)
            log.error(f"[RX {self._component_id}] recv_num_samps exception: {msg}")
            self._send_message({'action': 'restart'})
            return np.array([0.0])

    def _on_message_received(self, message: Dict):
        match message['action']:
            case 'new-ack':
                config = message['data']

                #wyciągam numer seryjny z wiadomości
                self._usrp_usb_sn = config.pop('usrp_serial', None)
                
                #nawiązuję fizyczne połączenie z urządzeniem USRP
                if not self._test_mode and self._usrp_usb_sn:
                    import uhd
                    global usrp
                    try:
                        usrp = uhd.usrp.MultiUSRP(f'serial={self._usrp_usb_sn}')
                        log.info(f"[RX {self._component_id}] Connected to USRP (SN: {self._usrp_usb_sn}).")
                    except Exception as ex:
                        #wywolanie narzedzia diagnostycznego UHD, zwrócenie raportu "UHD_FIND_DEVICES"
                        found_devices_dump = subprocess.getoutput("uhd_find_devices")
                        
                        log.error(f"[RX {self._component_id}] Failed to open USRP {self._usrp_usb_sn}. Error: {ex}")
                        
                        #wynik raportu przekazywany jest do kontrolera
                        self._send_message({
                            'action': 'hardware-error', 
                            'requested_serial': self._usrp_usb_sn,
                            'found_devices': found_devices_dump,
                            'error_message': str(ex)
                        })
                        
                        self._send_message({'action': 'restart'})
                        return
                    
                config_req = RxConfigChangeRequest(**config)
                self._configure_rx(config_req)
                self._send_message({'action': 'ready'})
            case 'configure':
                config =  message['data']
                config = RxConfigChangeRequest(**config)
                self._configure_rx(config)
                self._send_message({'action' : 'configure-ack'})
            case 'measure':
                config = message['data']
                result = self._measure(config)
                self._send_message({'action': 'measure-ack', 'data': result})
            case _:
                log.warning('this action is not defined!')

    def _configure_rx(self, config: RxConfigChangeRequest):
        if self._test_mode:
            log.info('(test mode) RX {} configured', self._component_id)
        
        self._frequency = config.frequency_hz
        self._samp_rate = config.samp_rate
        self._rx_gain = config.gain_db
        self._buffer_size = config.buffer_size
        self._N = config.repeats

        if not self._test_mode:
            log.info(f"RX Configured: Frequency = {self._frequency} Hz, Gain = {self._rx_gain} dB, sample rate = {self._samp_rate} S/s")
 


    def _measure(self, config: Dict) -> List[float]:
        if self._test_mode:
            result = -80 + np.random.rand() * 20
            self._avg_power_history = pow(10.0, self._avg_power_history / 10.0) * self._log_history_coeff
            self._avg_power_history += pow(10.0, result / 10.0) * (1.0 - self._log_history_coeff)
            self._avg_power_history = 10.0 * np.log10(self._avg_power_history)
            log.info(f"(test mode) Avg: {self._avg_power_history:.2f} dBm; Current: {result:.2f} dBm")
            if (np.random.rand() < self._parameters.test_mode_rx_fail_chance):
                self._send_message({'action': 'restart'})
                log.error('(test mode) RX failed')
                return [0.0]
            return [result] 
        else:
            power_measurements = []
            while len(power_measurements) < self._N:
                samples = self._recv_samples_safe()
                power_lin = np.mean(np.abs(samples) ** 2)
                power_log = 10 * np.log10(power_lin)
                power_measurements.append(float(power_log))

                self._avg_power_history = pow(10.0, self._avg_power_history / 10.0) * self._log_history_coeff
                self._avg_power_history += power_lin * (1.0 - self._log_history_coeff)
                self._avg_power_history = 10.0 * np.log10(self._avg_power_history)
                log.info(f"Avg: {self._avg_power_history:.2f} dBm; Current: {power_log:.2f} dBm")
            return power_measurements
