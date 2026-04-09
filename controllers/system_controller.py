
import time
import sys
from typing import Dict

from loguru import logger as log

from helpers.helpers import ZmqServer
from helpers.parameters import Parameters
from algorithms.system_logic import SystemLogic
from algorithms.algorithm import Algorithm
from algorithms.experiment import Experiment


class SystemController:
    def __init__(self,
                 parameters: Parameters,
                 algorithm: Algorithm,
                 experiment: Experiment
                 ):
        self._parameters = parameters
        log.info('SystemController initialized')
        
        self._connection = ZmqServer(
            port_pub=self._parameters.system_controller_port_pub_sub,
            port_pull=self._parameters.system_controller_port_push_pull
        )
        self._system_logic = SystemLogic(
            parameters=parameters,
            algorithm=algorithm,
            experiment=experiment
        )
        
        self._generator_id: str | None = None
        self._ris_ids: str[str] = set()
        self._rx_ids: str[str] = set()

    def _send_message(self, message: Dict):
        self._connection.send_message(message)

    def run(self) -> None:
        log.info("Waiting for all required components to register ...")
              
        start_time = time.time()        
        while not self._system_logic.ready():
            self._connection.receive_messages(self._handle_message_received)
            
            if time.time() - start_time > self._parameters.system_controller_wait_time_s:
                log.warning("Timeout: not all components registered.")
                self._send_message({'action': 'restart'})
                start_time = time.time()
                
        while not self._system_logic.finished():
            self._connection.receive_messages(self._handle_message_received)
            self._generate_messages()

        self._send_message({'action': 'done'})

        time.sleep(0.5) 
        
        if hasattr(self._connection, 'close'):
            self._connection.close()


        
    def _generate_messages(self):
        if self._system_logic.generate_measurement_command():
            log.debug('Start measurements')
            self._send_message({'component': 'rx', 'action': 'measure', 'data': {}})

        generator_request, rises_requests = self._system_logic.generate_configuration_change_requests()

        if generator_request is not None:
            if generator_request.transmission_enabled == self._parameters.generator_transmission_enabled and \
                generator_request.transmit_power_dbm == self._parameters.generator_transmit_power_dbm and \
                generator_request.frequency_hz == self._parameters.frequency_hz:
                log.debug('Skipping generator config update - no change detected.')
                self._system_logic.generator.received_ready('0')
            else:
                log.info("Updating generator configuration.")
                self._parameters.generator_transmission_enabled = generator_request.transmission_enabled
                self._parameters.generator_transmit_power_dbm = generator_request.transmit_power_dbm
                self._parameters.frequency_hz = generator_request.frequency_hz
                self._send_message({
                    'component':'generator', 
                    'action': 'configure', 
                    'data': {
                        'frequency_hz': self._parameters.frequency_hz,
                        'transmit_power_dbm': self._parameters.generator_transmit_power_dbm,
                        'transmission_enabled': self._parameters.generator_transmission_enabled
                    }})

        if rises_requests is not None:
            for ris_id, ris_request in rises_requests.items():
                if ris_request.pattern_index == self._parameters.ris_settings[ris_id][0] and \
                    ris_request.pattern_hex == self._parameters.ris_settings[ris_id][1]:
                    log.debug(f"Skipping RIS {ris_id} config update - no change detected.")
                    self._system_logic.rises.received_ready(ris_id)
                else:
                    log.info(f"Updating RIS {ris_id} configuration.")
                    self._parameters.ris_settings[ris_id] = (ris_request.pattern_index, ris_request.pattern_hex) 
                    log.debug('set RIS {} pattern {}', ris_id, ris_request.pattern_hex)
                    self._send_message({
                        'component': 'ris', 
                        'id': ris_id, 
                        'action': 'configure', 
                        'data': ris_request.model_dump()
                    })

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

        if 'id' in message and message['id'] is not None:
            self._generator_id = str(message['id'])

        match message['action']:
            case 'new':
                uid = message.get('_id')
                message['action'] = 'new-ack'
                message['data'] = self._system_logic.generator.received_new(device_id=message['id'], unique_id=uid)
                self._send_message(message)
            case 'ready':
                self._system_logic.generator.received_ready(device_id=message['id'])
                log.info('Generator is ready to operate.')
            case 'configure-ack':
                self._system_logic.generator.received_ready(device_id=message['id'])
                log.debug('Generator changed configuration.')
            case _:
                log.warning('Unknown generator action!')
 
    def _handle_ris_message_received(self, message: Dict): 
        if 'id' in message and message['id'] is not None:
            self._ris_ids.add(str(message['id'])) 
            
        match message['action']:
            case 'new':
                uid = message.get('_id')
                message['action'] = 'new-ack'
                message['data'] = self._system_logic.rises.received_new(device_id=message['id'], unique_id=uid)
                self._send_message(message)
            case 'ready':
                self._system_logic.rises.received_ready(device_id=message['id'])
                log.info('RIS {} is ready to operate.', message['id'])
            case 'configure-ack':
                self._system_logic.rises.received_ready(device_id=message['id'])
                log.debug('RIS {} changed configuration.', message['id'])
            case 'hardware-error':
                log.error(
                    "RIS {} hardware fault! Requested: {}. Error: {}. Actually found mapped devices: {}", 
                    message['id'], 
                    message.get('requested_port'), 
                    message.get('error_message'),
                    message.get('found_custom_devices')
                )
            case 'restart':
                log.error('RIS {} requested restart', message['id'])
                self._send_message({'action': 'restart'})
            case _:
                log.warning('Unknown RIS action!')
                

    def _handle_rx_message_received(self, message: Dict):
        
        if 'id' in message and message['id'] is not None:
            self._rx_ids.add(str(message['id']))

        match message['action']:
            case 'new':
                uid = message.get('_id')
                message['action'] = 'new-ack'
                message['data'] = self._system_logic.rxes.received_new(device_id=message['id'], unique_id=uid)
                self._send_message(message)
            case 'ready':
                self._system_logic.rxes.received_ready(device_id=message['id'])
                log.info('RX {} is ready to operate.', message['id'])
            case 'measure-ack':
                self._system_logic.rxes.received_ready(device_id=message['id'])
                self._system_logic.receive_measurement_results(device_id=message['id'], results=message['data'])

                log.debug('RX {} measured: {}', message['id'], message['data'])
            case 'hardware-error':
                log.error(
                    "RX {} hardware fault! Requested Serial: {}. Error: {}. UHD Report:\n{}", 
                    message['id'], 
                    message.get('requested_serial'), 
                    message.get('error_message'),
                    message.get('found_devices')
                )
            case "restart":
                log.error('RX {} requested restart', message['id'])
                self._send_message({'action': 'restart'})
            case _:
                log.warning('Unknown RX action')
    
