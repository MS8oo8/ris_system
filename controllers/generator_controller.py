import zmq
from loguru import logger as log
import time
#import json
from RsSmw import *
from RsSmbv import * 

from typing import Dict, Callable
from helpers.zmq_connection import ZmqClient
from controllers.controller import Controller
from helpers.parameters import GeneratorParams, Parameters, GeneratorModel


class GeneratorController(Controller):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._generator = None
        
        params = Parameters().get().generator 
        
        #self._select = params.select
        self._model = params.model
        self._con  = params.connection
        
        if self._con:
            self._mode = self._con.mode
            self._generator_model = self._con.generator_model
            self._frequency = self._con.frequency
            self._transmit_power = self._con.transmit_power
            self._transmission_enabled = self._con.transmission_enabled
            self._ip_address = self._con.ip_address
            self._port = self._con.port
            self._connection_type = self._con.connection_type


        if not self._test_mode:
            try:
                resource = f'TCPIP::{self._ip_address}::{self._port}::{self._connection_type}'
                if self._generator_model == GeneratorModel.SMM100A:
                    self._generator = RsSmw(resource, True, False, "SelectVisa='socket'")
                elif self._generator_model == GeneratorModel.SMBV100A:
                    self._generator = RsSmbv(resource, True, False, "SelectVisa='socket'")
                
                log.info(f"[INFO] Connected to generator {self._generator_model} at {resource}")
            except Exception as e:
                log.error(f"[ERROR] Error connecting to generator: {e}")
                exit()

    def _on_message_received(self, message: Dict):
        match message['action']:
            case 'new-ack':
                config = message['data']
                self._configure_generator(config)
                self._send_message({'action': 'ready'})
            case 'configure':
                config = message['data']
                self._configure_generator(config)
                self._send_message({'action': 'configure-ack'})
            case 'noise':
                self._configure_noise()
                self._send_message({'action': 'noise-ack'})
            case _:
                log.warning('this action is not defined!')

    def _configure_generator(self, config: Dict):
        print(config)
        if self._test_mode:
            log.info('(TEST) generator configured')
            return

        if 'frequency' in config:
            # change or set frequency
            self._frequency = config['frequency']

        if 'transmit_power' in config:
            # change or set transmit power
            self._transmit_power = config['transmit_power']

        if 'transmission_enabled' in config:
            # change or set transmision enabled
            self._transmission_enabled = config['transmission_enabled']
        
        if not self._test_mode and self._generator:
            if self._generator_model == GeneratorModel.SMM100A:
                #self._generator.source.bb.dm.set_state(True)
                self._generator.source.frequency.fixed.set_value(self._frequency)
                self._generator.source.power.level.immediate.set_amplitude(self._transmit_power)
                self._generator.output.state.set_value(self._transmission_enabled) 
            elif self._generator_model == GeneratorModel.SMBV100A:
                self._generator.source.frequency.fixed.set_value(self._frequency)
                self._generator.source.power.level.immediate.set_amplitude(self._transmit_power)
                self._generator.output.state.set_value(self._transmission_enabled)
                #self._generator.output.state.set_value(True) 
            
            # if self._mode == "wlan": # tu ustawia 
            #     #self._generator.source.bb.wlnn.set_value(True)
            #     self._generator.source.bb.wlnn.waveform.set_create("IEEE80211a")
            #     self._generator.source.bb.wlnn.set_bandwidth(bwidth=enums.WlannTxBw.BW20)
            # elif self._mode == 'dvbt': #jeszcze nie testowane
            #     self._generator.source.bb._dvb.set_standard("DVB")
            #     self._generator.source.bb._dvb.set_bandwidth(bwidth=enums.WlannTxBw.BW20)
            #     self._generator.source.bb.dvbt.state.set_value(True)
            #     self._generator.source.bb.dvbt.standard.set_value( "DVB-T")
            #     self._generator.source.bb.dvbt.bandwidth.set_value( 8e6)
            #     self._generator.source.bb.dvbt.modulation.set_value( "64QAM")
            #     self._generator.source.bb.dvbt.code_rate.set_value( "2/3")
            #     self._generator.source.bb.dvbt.guard_interval.set_value( "1/16")

                
            log.info(f"[GENERATOR] {self._generator_model} Configured: Frequency = {self._frequency} Hz, Power = {self._transmit_power} dBm, Enabled = {self._transmission_enabled}")
    
    def _noise(self):
        if self._test_mode:
            log.info('(TEST) Generator set to noise mode')
            return
        if not self._test_mode and self._generator:
            self._generator.output.state.set_value(False)
            log.info("[GENERATOR] Set to noise mode")









# if ON_WINDOWS:
#     print('Powiedzmy ze sie udalo')
# else:
#     try:
#         with open("config.json") as config_f:
#             RsSmw.assert_minimum_version('5.0.44')
#             config = json.load(config_f)
#             IP_ADDRESS_GENERATOR = config["IP_ADDRESS_GENERATOR"]
#             PORT = config["PORT"]
#             CONNECTION_TYPE = config["CONNECTION_TYPE"]
#             resource = f'TCPIP::{IP_ADDRESS_GENERATOR}::{PORT}::{CONNECTION_TYPE}'
#             try:
#                 print(f"[INFO] Łączenie z generatorem pod adresem: {resource}")
#                 generator = RsSmw(resource, True, True, "SelectVisa='socket'")
#                 print("[INFO] Połączono z generatorem.")
#             except Exception as e:
#                 print(f"[ERROR] Błąd podczas nawiązywania połączenia: {e}")
#                 exit()
#     except FileNotFoundError:
#         print("Brak pliku konfiguracyjnego. Upewnij się, że istnieje plik config.json.")
#         exit()


# def configure_generator(frequency, gain):
#     try:
#         if ON_WINDOWS:
#             print("[GENERATOR] Skonfigurowany")
#         else:

#             generator.source.bb.dm.set_state(True)
#             generator.source.frequency.fixed.set_value(frequency)
#             generator.source.power.level.immediate.set_amplitude(gain)
#             generator.output.state.set_value(True) 
#             print(f"[GENERATOR] Nadawanie sygnału rozpoczęte: Frequency = {frequency} Hz, Gain = {gain} dBm")
#     except Exception as e:
#         print(f"[GENERATOR ERROR] Nie można skonfigurować generatora: {e}")
#         raise

# def configure_noise():
#     try:
#         if ON_WINDOWS:
#             print("[GENERATOR] szum")
#         else:
#             generator.output.state.set_value(False)  
#             print("[GENERATOR] Generator ustawiony w trybie szumu.")
#     except Exception as e:
#         print(f"[GENERATOR ERROR] Nie można ustawić trybu szumu: {e}")
#         raise

# def stop_generator():
#     try:
#         if ON_WINDOWS:
#             print("[GENERATOR] Generator został wyłączony.")
#         else:
#             generator.output.state.set_value(False)
#             print("[GENERATOR] Generator został wyłączony.")
#     except Exception as e:
#         print(f"[GENERATOR ERROR] Nie można wyłączyć generatora: {e}")
#         raise

# def handle_messages():
#     try:
#         poller = zmq.Poller()
#         poller.register(socket_pull, zmq.POLLIN)

#         while True:
#             events = dict(poller.poll(timeout=100))  # 100 ms timeout
#             if socket_pull in events:
#                 message = socket_pull.recv().decode("utf-8")
#                 data = json.loads(message)
#                 print(f"[GENERATOR] Otrzymano wiadomość: {data}")

#                 action = data.get("action")
                
#                 if action == "now":
#                     action = data.get("action")
#                     frequency = data.get("frequency")
#                     gain = data.get("gain")
#                     configure_generator(frequency, gain)
#                     socket_push.send(json.dumps({"component": "generator", "status": "configured"}).encode("utf-8"))
#                     print("[GENERATOR] Generator pozostaje w stanie nadawania.")
#                 elif action == "noise":
#                     configure_noise()
#                     socket_push.send(json.dumps({"component": "generator", "status": "noise_mode"}).encode("utf-8"))

#                 elif action == "off":
#                     stop_generator()
#                     socket_push.send(json.dumps({"component": "generator", "status": "stopped"}).encode("utf-8"))

#                 else:
#                     print(f"[GENERATOR] Nieznana akcja: {action}")

#     except KeyboardInterrupt:
#         print("\n[GENERATOR] Zatrzymano program.")
#         stop_generator()
#     except Exception as e:
#         print(f"[GENERATOR ERROR] {e}")
#         stop_generator()

# if __name__ == "__main__":
#     try:
#         socket_push.send(json.dumps({"component": "generator", "action": "ready"}).encode("utf-8"))
#         print("[GENERATOR] Generator gotowy do pracy.")
#         handle_messages()
#     except KeyboardInterrupt:
#         print("\n[GENERATOR] Zatrzymano program.")
#         stop_generator()
#     except Exception as e:
#         print(f"[GENERATOR ERROR] {e}")
#         stop_generator()
