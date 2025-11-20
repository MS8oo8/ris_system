from time import time
from typing import Dict

from loguru import logger as log

from helpers.helpers import ZmqClient, RestartRequired
from helpers.parameters import Parameters


class Controller:
    def __init__(self,
                 parameters: Parameters,
                 component_name: str,
                 component_id: str,
                 # controller_address: str,
                 # port_sub: int,
                 # port_push: int,
                 # test_mode: bool
                 ):
        self._parameters = parameters
        self._component_name = component_name
        self._component_id = component_id
        self._id = int(time() * 1000)
        self._connected = False
        self._connection = ZmqClient(
            address_system_controller=self._parameters.system_controller_ip_address,
            port_sub=self._parameters.system_controller_port_pub_sub,
            port_push=self._parameters.system_controller_port_push_pull
        )
        self._test_mode = self._parameters.test_mode

    def run(self):
        keep_running = True
        self._send_message({'action': 'new', '_id': self._id})
        while keep_running:
            self._connection.receive_messages(
                on_message_received=self._on_message_received_base
            )

    def _on_message_received(self, message: Dict) -> None:
        raise NotImplementedError
    
    def _on_finish(self) -> None:
        log.warning('Component {} ({}) finished', self._component_name, self._component_id)

    def _on_message_received_base(self, message: Dict) -> None:

        if not self._connected:
            if message['action'] == 'new-ack':
                self._connected = True
                log.debug('Component {} connected', self._component_name)
            else:
                log.warning('Component {} NOT connected', self._component_name)

        if message['action'] in ['restart', 'reinit']:
            log.warning('Component {} restarting as requested', self._component_name)
            raise RestartRequired
        
        if message['action'] == 'done':
            self._on_finish()
            return

        if message['component'] != self._component_name:
            return

        if 'id' in message and message['id'] != self._component_id:
            return

        log.debug('Component {} received: {}', self._component_name, message)
        self._on_message_received(message)

    def _send_message(self, message: Dict) -> None:
        message['_id'] = str(self._id)
        message['component'] = self._component_name
        message['id'] = self._component_id 

        self._connection.send_message(message)
        log.debug('Component {} send: {}', self._component_name, message)

