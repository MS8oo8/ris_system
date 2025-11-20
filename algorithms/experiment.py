import os
from datetime import datetime
from typing import List, Optional

import numpy as np
import pandas as pd
from loguru import logger as log

from helpers.parameters import Parameters, GeneratorConfigChangeRequest


class Experiment:

    def __init__(self, parameters: Parameters):
        self._parameters = parameters

    def finished(self) -> bool:
        raise NotImplementedError

    def generate_generator_params(self) -> GeneratorConfigChangeRequest | None:
        raise NotImplementedError

    def store_results(self, device_id: str, results) -> None:
        raise NotImplementedError
    
    def reset(self) -> None:
        raise NotImplementedError


class ExampleExperiment(Experiment):

    def __init__(self,
        parameters: Parameters,
        power_setup: Optional[List[float | None]] = None,
        results_dir: str = "results",
    ):
        super().__init__(parameters=parameters)

        self._power_setup: List[float | None] = power_setup if power_setup is not None else [-15.0]
        self._itr = 0
        self._rx_count = self._parameters.rx_count
        self._data = np.nan * np.ones((self._rx_count, len(self._power_setup)))
        self._waiting_for = 0
        self._results_dir = results_dir

    def reset(self) -> None:
        self._itr = 0
        self._data[:] = np.nan

    def finished(self):
        return self._itr == len(self._power_setup) and not np.isnan(self._data).any()

    def generate_generator_params(self) -> GeneratorConfigChangeRequest | None:
        log.info('1AAAAA {}', self._waiting_for)
        if self._waiting_for > 0:
            return None

        log.debug('Experiment step {}/{}: power {} ', 
                self._itr + 1, len(self._power_setup), self._power_setup[self._itr])

        generator_requests = GeneratorConfigChangeRequest(
            frequency_hz=self._parameters.frequency_hz,
            transmit_power_dbm=self._power_setup[self._itr],
            transmission_enabled=self._power_setup[self._itr] is not None
        )
        log.info('2AAAAA {}', self._waiting_for)
        self._waiting_for = self._rx_count

        return generator_requests

    def store_results(self, device_id: str, results) -> None:
        assert self._waiting_for > 0

        rx_id = int(device_id)
        mean_result = float(np.mean(results))
        power = self._power_setup[self._itr]

        timestamp = datetime.now().strftime("%Y%m%d")
        results_dir = "results"
        os.makedirs(results_dir, exist_ok=True)
        filename = os.path.join(results_dir, f"live_experiment_rx_{rx_id}_{timestamp}.csv")

        row = {
            "Timestamp": datetime.now().isoformat(),
            "Step": self._itr + 1,
            "Power": "Noise" if power is None else power,
            "Result": mean_result
        }

        df = pd.DataFrame([row])
        df.to_csv(filename, mode='a', header=not os.path.exists(filename), index=False)

        self._data[rx_id, self._itr] = mean_result
        log.info('3AAAAA {}', self._waiting_for)
        self._waiting_for -= 1
        log.info('4AAAAA {}', self._waiting_for)
        if self._waiting_for == 0:
            log.info('HEREEEEA {}', self._waiting_for)
            self._itr += 1

        log.info('aaaaaaA:{}', self._itr)

