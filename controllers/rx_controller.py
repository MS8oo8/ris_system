import zmq
from loguru import logger as log
# import time
import json
# from RsSmw import *

import numpy as np
from typing import Dict, Callable, List
from helpers.zmq_connection import ZmqClient
from controllers.controller import Controller
import time


usrp = None 


class RxController(Controller):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._frequency = None
        self._samp_rate = None
        self._rx_gain = None
        self._buffer_size = None #327680
        self._N = None #8

        if self._test_mode:
            print(f"Symulacja połączenia z USRP")
        else:
            #time.sleep(10)
            import uhd
            global usrp
            if self._component_id == '0':
            	usrp = uhd.usrp.MultiUSRP("serial=3273AD8")
            # elif self._component_id == '1':
           # 	usrp = uhd.usrp.MultiUSRP("serial=3273ACF")


    def _on_message_received(self, message: Dict):
        match message['action']:
            case 'new-ack':
                config = message['data']
                self._configure_rx(config)
                self._send_message({'action': 'ready'})
            case 'measure':
                config = message['data']
                result = self._measure(config)
                self._send_message({'action': 'measure-ack', 'data': result})
            case _:
                log.warning('this action is not defined!')

    def _configure_rx(self, config: Dict):
        if self._test_mode:
            log.info('(TEST) RX {} configured', self._component_id)
            return

        if 'frequency' in config:
            # set or update frequency
            self._frequency = config['frequency']

        if 'samp_rate' in config:
            # set or update sampling rate
            self._samp_rate = config['samp_rate']

        if 'rx_gain' in config:
            # set or update rx gain
            self._rx_gain = config['rx_gain']
            
        if 'buffer_size' in config:
            self._buffer_size = config['buffer_size']
            
        if 'N' in config: #gdzie w innym miejscu N zalezna jest od tego inijka 78
            self._N = config['N']
        
        if self._test_mode ==  False:
        #     #configure usrp
            # self.usrp.set_rx_rate(self._samp_rate)
            # self.usrp.set_rx_freq(self._frequency,1)
            # self.usrp.set_rx_gain(self._rx_gain,1)
            log.info(f"RX Configured: Frequency = {self._frequency} Hz, Gain = {self._rx_gain} dB, sample rate = {self._samp_rate} S/s")
            #time.sleep(10)


    def _measure(self, config: Dict) -> List[float]:
        if self._test_mode:
            log.info('(TEST) RX {} measurement in progress', self._component_id)
            return [-68.8] #symulation
        
        power_measurements = []
        while len(power_measurements) < self._N:
            #print(self._buffer_size, self._frequency, self._samp_rate, self._rx_gain)
            samples = usrp.recv_num_samps(self._buffer_size, self._frequency, self._samp_rate, [0], self._rx_gain)
            #samples = [30.0, 12.2,23.0]
            power_lin = np.mean(np.abs(samples) ** 2)
            power_log = 10 * np.log10(power_lin)
            power_measurements.append(float(power_log))
        
        log.info(f"Measured {self._N} power samples")
        return power_measurements
