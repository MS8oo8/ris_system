import numpy as np
from loguru import logger as log
from typing import List, Dict, Tuple
from helpers.parameters import Parameters, GeneratorParams, RisParams
from algorithms.algorithm import Algorithm
from algorithms.experiment import Experiment


class DeviceHandler:

    def ready(self) -> bool:
        raise NotImplementedError

    def received_new(self, device_id: str, unique_id: str) -> Dict | None:
        raise NotImplementedError

    def received_ready(self, device_id: str) -> None:
        raise NotImplementedError

    def wait(self, device_id: str | None = None) -> None:
        raise NotImplementedError


class GeneratorHandler(DeviceHandler):
    def __init__(self):
        self._id = None
        self._config = None
        self._ready = False

    def ready(self):
        return self._ready

    def received_new(self, device_id, unique_id) -> Dict | None:
        assert self._id is None

        self._id = device_id
        self._config = {
            'frequency': Parameters().get().frequency,
            'transmit_power': Parameters().get().generator.connection.transmit_power,
            'transmission_enabled': Parameters().get().generator.connection.transmission_enabled
        }
        return self._config

    def received_ready(self, device_id) -> None:
        assert self._id == device_id
        self._ready = True

    def wait(self, device_id: str | None = None) -> None:
        self._ready = False


class RisesHandler(DeviceHandler):
    def __init__(self):
        self._ready = {ris: False for ris in Parameters().get().rises}

    def ready(self):
        return all(self._ready.values())

    def received_new(self, device_id, unique_id) -> Dict | None:
        assert device_id in self._ready
        log.info("Registered new RIS: {}", device_id)

        return None

    def received_ready(self, device_id) -> None:
        assert device_id in self._ready
        self._ready[device_id] = True

    def wait(self, device_id: str | None = None) -> None:
        for ris_id in self._ready.keys():
            self._ready[ris_id] = False


class RxesHandler(DeviceHandler):
    def __init__(self):
        self._ready = {}

    def ready(self):
        return len(self._ready) == Parameters().get().rxes.count and \
            all(self._ready.values())

    def received_new(self, device_id, unique_id) -> Dict | None:
        assert len(self._ready) <= Parameters().get().rxes.count
        log.info("Registered new RX: {}", device_id)


        self._ready[device_id] = False
        return {
            'frequency': Parameters().get().frequency,
            'samp_rate': Parameters().get().rxes.samp_rate,
            'rx_gain': Parameters().get().rxes.rx_gain,
            'buffer_size' : Parameters().get().rxes.buffer_size,
            'N' : Parameters().get().rxes.N
        }

    def received_ready(self, device_id) -> None:
        assert device_id in self._ready
        self._ready[device_id] = True

    def wait(self, device_id: str | None = None) -> None:
        for rx_id in self._ready:
            assert self._ready[rx_id]
            self._ready[rx_id] = False


class SystemLogic:

    def __init__(self, algorithm: Algorithm, experiment: Experiment):
        self.generator = GeneratorHandler()
        self.rises = RisesHandler()
        self.rxes = RxesHandler()
        self._algorithm = algorithm
        # self._algorithm.attach_rx_handler(self.rxes)
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


    def generate_configuration_change_requests(self) -> Tuple[GeneratorParams | None, Dict[str, RisParams] | None]:

        if not self.ready() or self._measurment_queued:
            #log.info(f'Check: ready = {self.ready()}, queued={self._measurment_queued} ')
            return (None, None)



        if not self._algorithm.data_collection_finished():
            request = self._algorithm.data_collection_request()

            self.generator.wait()
            self.rises.wait()
            self._measurment_queued = True

            return request

        if self._data_collection_phase:
            log.info('Finished data collection phase. Starting experiment phase.') 
            self._data_collection_phase = False



        if not self._experiment.finished():
            request_generator = self._experiment.generate_generator_params()
            self.generator.wait()
            request_rises = self._algorithm.algorithm_step()
            self.rises.wait()
            self._measurment_queued = True
            return request_generator, request_rises


        if self._experiment.finished():
            log.info('Experiment finished. Start next cycle of algorithm phase')
            self._data_collection_phase = True
            self._measurment_queued = False
            self._algorithm.data = np.full(
                (
                    self._algorithm._rx_count,
                    self._algorithm.configs.shape[0],
                    len(self._algorithm.signal_power)
                ),
                np.nan,
                dtype = float
            )
            self._algorithm.waiting_for = self._algorithm._rx_count
            #self._measurment_queued = False
            log.info(f'Reset algorithm data to nan: \n{self._algorithm.data}')


        return (None, None)  # FINISHED

 

    def receive_measurement_results(self, device_id: str, results: Dict) -> None:
        if self._data_collection_phase:
            self._algorithm.store_results(device_id, results)
            log.info("Got algorithm measurement from {}: {}", device_id, results)
        else:
            self._experiment.store_results(device_id, results)
            log.info("Got experiment measurement from {}: {}", device_id, results)
