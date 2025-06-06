import zmq
import numpy as np
# from enum import StrEnum
from typing import Dict, Callable
from loguru import logger as log

from helpers.zmq_connection import ZmqServer
from helpers.parameters import Parameters
from algorithms.system_logic import SystemLogic
from algorithms.algorithm import Algorithm
from algorithms.experiment import Experiment


from prometheus_client import Gauge, Info
g_rx_power = Gauge('rx_power', 'Description of gauge', labelnames=['rx'])
g_rx_power_by_pattern = Gauge('rx_power_by_pattern', 'Description of gauge', labelnames=['ris_0'])
g_selected_pattern = Gauge('selected_pattern', 'Description of gauge', labelnames=['ris_0'])
g_info = Info('selected_pattern_png', 'description', labelnames=['ris_id'])
g_selected_pattern_index = Gauge('selected_pattern_index', 'description', labelnames=['ris_id'])

class SystemController:
    def __init__(self,
                 port_pub: int,
                 port_pull: int,
                 algorithm: Algorithm,
                 experiment: Experiment
                 ):
        log.info('SystemController created')
        self._connection = ZmqServer(
            port_pub=port_pub,
            port_pull=port_pull
        )
        self._system_logic = SystemLogic(
            algorithm=algorithm,
            experiment=experiment
        )

    def run(self) -> None:
        while not self._system_logic.finished():
            self._connection.receive_messages(self._handle_message_received)
            self._generate_messages()

            import time
            # time.sleep(1)

    def _generate_messages(self):
        if self._system_logic.generate_measurement_command():
            log.debug('Start measurements')
            self._send_message({'component': 'rx', 'action': 'measure', 'data': {}})

        generator_request, rises_requests = self._system_logic.generate_configuration_change_requests()
        # result = self._system_logic.generate_configuration_change_requests()
        # if result is None:
        #     # print("=================================================")
        #     generator_request, rises_requests = None, None
        # else:
        #     # print("WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWw")
        #     generator_request, rises_requests = result
        #     # print(f'generator: {generator_request}')
        #     # print(f'ris: {rises_requests}')


        if generator_request is not None:
            if generator_request == Parameters().get().generator:
                log.debug('skip - generator configuration the same')
                self._system_logic.generator.received_ready('0')
            else:
                Parameters().get().generator = generator_request 
                self._send_message({'component':'generator', 'action': 'configure', 'data': {
                    
                        'frequency': Parameters().get().frequency,
                        'transmit_power': Parameters().get().generator.connection.transmit_power,
                        'transmission_enabled': Parameters().get().generator.connection.transmission_enabled
                    
                } })

        if rises_requests is not None:
            for ris_id, ris_request in rises_requests.items():
                if ris_request == Parameters().get().rises[ris_id]:
                    log.debug('skip - RIS {} configuration the same', ris_id)
                    self._system_logic.rises.received_ready(ris_id)
                else:
                    Parameters().get().rises[ris_id] = ris_request
                    log.debug('set RIS {} pattern {}', ris_id, ris_request.pattern)
                    self._send_message({'component': 'ris', 'id': ris_id, 'action': 'configure', 'data': ris_request.model_dump()})

    def _send_message(self, message: Dict):
        self._connection.send_message(message)

    def _handle_message_received(self, message: Dict):
        log.debug('Received {}', message)
        if message['component'] == 'generator':
            self._handle_generator_message_received(message)
        elif message['component'] == 'ris':
            self._handle_ris_message_received(message)
        elif message['component'] == 'rx':
            self._handle_rx_message_received(message)
        else:
            log.warning('no handler defined for this component!')

    def _handle_generator_message_received(self, message: Dict):
        match message['action']:
            case 'new':
                message['action'] = 'new-ack'
                message['data'] = self._system_logic.generator.received_new(device_id=message['id'], unique_id=message['_id'])
                self._send_message(message)
            case 'ready':
                self._system_logic.generator.received_ready(device_id=message['id'])
                log.info('Generator is ready to operate.')
            case 'configure-ack':
                self._system_logic.generator.received_ready(device_id=message['id'])
                log.debug('Generator changed configuration.')
            case _:
                log.warning('no handler defined for this action!')
 
    def _handle_ris_message_received(self, message: Dict): 
        match message['action']:
            case 'new':
                message['action'] = 'new-ack'
                message['data'] = self._system_logic.rises.received_new(device_id=message['id'], unique_id=message['_id'])
                self._send_message(message)
            case 'ready':
                self._system_logic.rises.received_ready(device_id=message['id'])
                log.info('RIS {} is ready to operate.', message['id'])
            case 'configure-ack':
                self._system_logic.rises.received_ready(device_id=message['id'])
                log.debug('RIS {} changed configuration.', message['id'])
            case _:
                log.warning('no handler defined for this action!')

    def _handle_rx_message_received(self, message: Dict):
        match message['action']:
            case 'new':
                message['action'] = 'new-ack'
                message['data'] = self._system_logic.rxes.received_new(device_id=message['id'], unique_id=message['_id'])
                self._send_message(message)
            case 'ready':
                self._system_logic.rxes.received_ready(device_id=message['id'])
                log.info('RX {} is ready to operate.', message['id'])
            case 'measure-ack':
                self._system_logic.rxes.received_ready(device_id=message['id'])
                self._system_logic.receive_measurement_results(device_id=message['id'], results=message['data'])

                # display prometheus
                value_rx_power = float(np.mean(message['data']))
                ris_0_pattern = Parameters().get().rises['0'].index
                # ris_1_pattern = Parameters().get().rises['1'].index
                selected = self._system_logic._algorithm.selected_config

                g_rx_power.labels(rx=0).set(value_rx_power)
                
                g_rx_power_by_pattern.labels(ris_0=str(ris_0_pattern).zfill(2)).set(value_rx_power)

                for i in range(len(self._system_logic._algorithm.configs)):
                    g_selected_pattern.labels(ris_0=str(i).zfill(2)).set(0)
                if selected is not None and selected == ris_0_pattern:
                    g_selected_pattern.labels(ris_0=str(ris_0_pattern).zfill(2)).set(1)
                    g_info.labels(ris_id=0).info({'path': f'{str(ris_0_pattern).zfill(2)}.png' })
                    g_selected_pattern_index.labels(ris_id=0).set(ris_0_pattern)
                # end of display

                log.debug('RX {} measured: {}', message['id'], message['data'])
            case _:
                log.warning('no handler defined for this action!')