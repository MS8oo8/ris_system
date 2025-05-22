from loguru import logger as log
import json
import zmq

from typing import Callable, Dict


class ZmqBase:

    def __init__(self,
                 timeout_ms: int = 100
                 ):
        self._timeout_ms = timeout_ms

        self._poller = zmq.Poller()
        self._context = zmq.Context()

    def receive_messages(self, 
                         on_message_received: Callable,
                         ) -> None:
        raise NotImplementedError

    def send_message(self, message: Dict) -> None:
        raise NotImplementedError

    def _decode_message(self, message: bytes) -> Dict:
        return json.loads(message.decode('utf-8'))

    def _encode_message(self, message: Dict) -> bytes:
        return json.dumps(message).encode('utf-8')

    def _poll(self) -> Dict:
        return dict(self._poller.poll(timeout=self._timeout_ms))


class ZmqServer(ZmqBase):
    def __init__(self,
                 port_pub: int | None = None,
                 port_pull: int | None = None,
                 timeout_ms: int = 100
                 ):
        super().__init__(timeout_ms)

        self._socket_pub = self._create_and_bind_socket(
            port_pub, zmq.PUB
        )
        self._socket_pull = self._create_and_bind_socket(
            port_pull, zmq.PULL
        )

    def receive_messages(self, 
                         on_message_received: Callable,
                         ) -> None:
        sockets = self._poll()

        if self._socket_pull in sockets:
            on_message_received(self._decode_message(self._socket_pull.recv()))

    def send_message(self, message: Dict) -> None:
        if self._socket_pub is None:
            raise ValueError('Push socket not configured!')
        log.debug('Sending {}', message)
        self._socket_pub.send(self._encode_message(message))

    def _create_and_bind_socket(self, port: int, socket_type: int) -> zmq.Socket | None:
        if port is None:
            return None
        socket = self._context.socket(socket_type)
        socket.bind(
             f"tcp://*:{port}"
        )
        if socket_type == zmq.PULL:
            self._poller.register(socket, zmq.POLLIN)
        return socket


class ZmqClient(ZmqBase):
    def __init__(self,
                 address_system_controller: str,
                 port_sub: int | None = None,
                 port_push: int | None = None,
                 timeout_ms: int = 100
                 ):
        super().__init__(timeout_ms)

        self._socket_sub = self._create_and_connect_socket(
            address_system_controller, port_sub, zmq.SUB
        )
        self._socket_push = self._create_and_connect_socket(
            address_system_controller, port_push, zmq.PUSH
        )

    def receive_messages(self, 
                         on_message_received: Callable,
                         ) -> None:
        sockets = self._poll()

        if self._socket_sub in sockets:
            on_message_received(self._decode_message(self._socket_sub.recv()))

    def send_message(self, message: Dict) -> None:
        if self._socket_push is None:
            raise ValueError('Push socket not configured!')
        self._socket_push.send(self._encode_message(message))

    def _create_and_connect_socket(self, address: str, port: int, socket_type: int) -> zmq.Socket | None:
        if port is None:
            return None
        socket = self._context.socket(socket_type)
        socket.connect(
             f"tcp://{address}:{port}"
        )
        if socket_type == zmq.SUB:
            socket.setsockopt_string(zmq.SUBSCRIBE, "")
            self._poller.register(socket, zmq.POLLIN)
        return socket
