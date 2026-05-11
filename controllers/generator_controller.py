from typing import Dict

from loguru import logger as log

from controllers.controller import Controller
from helpers.parameters import GeneratorModel, GeneratorConfigChangeRequest


class GeneratorController(Controller):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._generator = None
             
        self._model = self._parameters.generator_selected_model
  
        self._frequency = self._parameters.frequency_hz
        self._transmit_power = self._parameters.generator_transmit_power_dbm
        self._transmission_enabled = self._parameters.generator_transmission_enabled
        
        if not self._test_mode:
            resource = f"TCPIP::{self._parameters.generator_ip_address}::{self._parameters.generator_port}::SOCKET"

            # resource = 'TCPIP::{self._ip_address}::{self._port}::{self._connection_type}'.format(
            #     self._parameters.generator_ip_address, self._parameters.generator_port, "SOCKET"
            # ) w tak zapisanym resource on ma problem: in __init__
            # resource = 'TCPIP::{self._ip_address}::{self._port}::{self._connection_type}'.format(
            # KeyError: 'self'

            try:
                if self._model == GeneratorModel.SMM100A:
                    from RsSmw import RsSmw
                    self._generator = RsSmw(resource, True, False, "SelectVisa='socket'")
                elif self._model == GeneratorModel.SMBV100A:
                    from RsSmbv import RsSmbv 
                    self._generator = RsSmbv(resource, True, False, "SelectVisa='socket'")
                else:
                    raise Exception(f"Unknown generator model: {self._model}")
                
                log.info(f"Connected to generator {self._model} at {resource}")
            except Exception as e:
                log.error(f"Error connecting to generator: {e}")
                exit()

    def _on_message_received(self, message: Dict):
        match message['action']:
            case 'new-ack':
                config = message['data']
                config = GeneratorConfigChangeRequest(**config)
                self._configure_generator(config)
                self._send_message({'action': 'ready'})
            case 'configure':
                config = message['data']
                config = GeneratorConfigChangeRequest(**config)
                self._configure_generator(config)
                self._send_message({'action': 'configure-ack'})
            case _:
                log.warning('this action is not defined!')

    def _configure_generator(self, config: GeneratorConfigChangeRequest):
        if self._test_mode:
            log.info('(test mode) generator configured {}'.format(config))
            return

        self._frequency = config.frequency_hz
        log.debug('Frequency set to {}', self._frequency)

        if config.transmit_power_dbm is not None:
            self._transmit_power = config.transmit_power_dbm
            log.debug('Transmit power set to {}', self._transmit_power)
        
        self._transmission_enabled = config.transmission_enabled
        log.debug('Transmission enabled set to {}', self._transmission_enabled)
        
        if not self._test_mode and self._generator:
            if self._model == "SMM100A":
                self._generator.source.frequency.fixed.set_value(self._frequency)
                self._generator.source.power.level.immediate.set_amplitude(self._transmit_power)
                self._generator.output.state.set_value(self._transmission_enabled) 
            elif self._model == "SMBV100A":
                self._generator.source.frequency.fixed.set_value(self._frequency)
                self._generator.source.power.level.immediate.set_amplitude(self._transmit_power)
                self._generator.output.state.set_value(self._transmission_enabled)

            log.info(f"[GENERATOR] {self._model} Configured: Frequency = {self._frequency} Hz, Power = {self._transmit_power} dBm, Enabled = {self._transmission_enabled}")