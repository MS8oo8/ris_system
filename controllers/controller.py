from time import time
from loguru import logger as log
from helpers.zmq_connection import ZmqClient
from typing import Dict


class Controller:
    def __init__(self,
                 component_name: str,
                 component_id: str,
                 controller_address: str,
                 port_sub: int,
                 port_push: int,
                 test_mode: bool
                 ):
        self._component_name = component_name
        self._component_id = component_id
        self._id = int(time() * 1000)
        self._connected = False
        self._connection = ZmqClient(
            address_system_controller=controller_address,
            port_sub=port_sub,
            port_push=port_push
        )
        self._test_mode = test_mode

    def run(self):
        keep_running = True
        self._send_message({'action': 'new', '_id': self._id})
        while keep_running:
            self._connection.receive_messages(
                on_message_received=self._on_message_received_base
            )

    def _on_message_received(self, message: Dict) -> None:
        raise NotImplementedError

    def _on_message_received_base(self, message: Dict) -> None:

        # READY ack should be received
        if not self._connected:
            if message['action'] == 'new-ack':
                self._connected = True
                log.debug('Component {} connected', self._component_name)
            else:
                log.warning('Component {} NOT connected', self._component_name)

        # FILTER messages from system controller
        if message['component'] != self._component_name:
            return

        # FILTER individual messages
        if 'id' in message and message['id'] != self._component_id:
            return

        log.debug('Component {} received: {}', self._component_name, message)
        self._on_message_received(message)

    def _send_message(self, message: Dict) -> None:
        message['component'] = self._component_name
        message['id'] = self._component_id
        self._connection.send_message(message)
        log.debug('Component {} send: {}', self._component_name, message)

