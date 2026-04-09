from typing import Dict, Tuple

from loguru import logger as log

from helpers.parameters import Parameters, GeneratorConfigChangeRequest, RisConfigChangeRequest
from algorithms.algorithm import Algorithm
from algorithms.experiment import Experiment


class DeviceHandler:

    def __init__(self, parameters: Parameters):
        self._parameters = parameters

    def ready(self) -> bool:
        raise NotImplementedError

    def received_new(self, device_id: str, unique_id: str) -> Dict | None:
        raise NotImplementedError

    def received_ready(self, device_id: str) -> None:
        raise NotImplementedError

    def wait(self, device_id: str | None = None) -> None:
        raise NotImplementedError


class GeneratorHandler(DeviceHandler):
    def __init__(self, parameters: Parameters):
        super().__init__(parameters=parameters)
        self._id = None
        self._config = None
        self._ready = False

    def ready(self):
        return self._ready

    def received_new(self, device_id, unique_id) -> Dict | None:
        self._id = device_id
        self._config = {
            'frequency_hz':self._parameters.frequency_hz,
            'transmit_power_dbm': self._parameters.generator_transmit_power_dbm,
            'transmission_enabled': self._parameters.generator_transmission_enabled
        }
        return self._config

    def received_ready(self, device_id) -> None:
        assert self._id == device_id
        self._ready = True

    def wait(self, device_id: str | None = None) -> None:
        self._ready = False


class RisesHandler(DeviceHandler):
    def __init__(self, parameters: Parameters):
        super().__init__(parameters=parameters)
        self._ready = {str(ris): False for ris in range(self._parameters.ris_count)}

    def ready(self):
        return all(self._ready.values())

    def received_new(self, device_id, unique_id) -> Dict | None:
        assert device_id in self._ready
        log.info("Registered new RIS: {}", device_id)

        #wcześniej tu było return None, zwrot parametrów transmisji w kontrolerze RIS
        return {
            'serial_port': self._parameters.ris_serial_map[device_id],
            'baudrate': self._parameters.ris_serial_boudrate,
            'timeout': self._parameters.ris_serial_timeout
        }

    def received_ready(self, device_id) -> None:
        assert device_id in self._ready
        self._ready[device_id] = True

    def wait(self, device_id: str | None = None) -> None:
        for ris_id in self._ready.keys():
            self._ready[ris_id] = False


class RxesHandler(DeviceHandler):
    def __init__(self, parameters: Parameters):
        super().__init__(parameters=parameters)
        self._ready = {}

    def ready(self):
        return len(self._ready) == self._parameters.rx_count and \
            all(self._ready.values())

    def received_new(self, device_id, unique_id) -> Dict | None:
        assert len(self._ready) <= self._parameters.rx_count
        log.info("Registered new RX: {}", device_id)


        self._ready[device_id] = False
        return {
            'usrp_serial': self._parameters.rx_usrp_serial_map[device_id],
            'frequency_hz': self._parameters.frequency_hz,
            'samp_rate': self._parameters.rx_samp_rate,
            'gain_db': self._parameters.rx_gain_db,
            'buffer_size' : self._parameters.rx_buffer_size,
            'repeats' : self._parameters.rx_repeats
        }

    def received_ready(self, device_id) -> None:
        assert device_id in self._ready
        self._ready[device_id] = True

    def wait(self, device_id: str | None = None) -> None:
        for rx_id in self._ready:
            assert self._ready[rx_id]
            self._ready[rx_id] = False


class SystemLogic:

    def __init__(self, parameters: Parameters, algorithm: Algorithm, experiment: Experiment):
        self._parameters = parameters
        self.generator = GeneratorHandler(parameters=parameters)
        self.rises = RisesHandler(parameters=parameters)
        self.rxes = RxesHandler(parameters=parameters)
        self._algorithm = algorithm
        self._experiment = experiment
        self._data_collection_phase = True
        self._measurment_queued = False

    def ready(self) -> bool:
        return all([self.generator.ready(), self.rises.ready(), self.rxes.ready()]) 

    def finished(self) -> bool:
        return self._experiment.finished()

    def generate_measurement_command(self) -> bool:
        if not self.ready():
            return False

        if self._measurment_queued:
            self._measurment_queued = False
            self.rxes.wait()
            return True
        
        return False
        
    def generate_configuration_change_requests(self) -> Tuple[GeneratorConfigChangeRequest | None, Dict[str, RisConfigChangeRequest] | None]:
        if not self.ready() or self._measurment_queued:
            return (None, None)

        if not self._algorithm.data_collection_finished():
            request = self._algorithm.data_collection_request()

            if request is None:
                return (None, None)

            gen_req, ris_req = request
            self.generator.wait()
            self.rises.wait()
            self._measurment_queued = True

            return gen_req, ris_req

        if self._data_collection_phase:
            log.info('Starting experiment phase.') 
            self._data_collection_phase = False

        if not self._experiment.finished():
            request_generator = self._experiment.generate_generator_params()
            self.generator.wait()
            request_rises = self._algorithm.algorithm_step()
            self.rises.wait()
            self._measurment_queued = True
            return request_generator, request_rises

        return (None, None)  

    def receive_measurement_results(self, device_id: str, results: Dict) -> None:
        if self._data_collection_phase:
            self._algorithm.store_results(device_id, results)
            log.info("Got algorithm measurement from {}: {}", device_id, results)
        else:
            self._experiment.store_results(device_id, results)
            log.info("Got experiment measurement from {}: {}", device_id, results)

