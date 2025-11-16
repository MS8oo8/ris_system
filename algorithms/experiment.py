from loguru import logger as log
from helpers.parameters import Parameters, GeneratorParams, GeneratorConnection
import numpy as np
from copy import deepcopy
import os
import pandas as pd
from datetime import datetime
from typing import List, Optional, Union


class Experiment:
    def finished(self) -> bool:
        raise NotImplementedError

    def generate_generator_params(self) -> GeneratorParams | None:
        raise NotImplementedError

    def store_results(self, device_id: str, results) -> None:
        raise NotImplementedError
    
    def reset(self) -> None:
        raise NotImplementedError


class ExampleExperiment(Experiment):

    def __init__(self,
        power_setup: Optional[List[Union[float, None]]] = None,
        results_dir: str = "results",
    ):
        self._power_setup: List[Union[float, None]] = power_setup if power_setup is not None else [-15.0]
        #self._power_setup = [-15.0]
        self._itr = 0
        self._rx_count = Parameters().get().rxes.count
        self._data = np.nan * np.ones((self._rx_count, len(self._power_setup)))
        self._waiting_for = 0
        self._results_dir = results_dir

    def reset(self) -> None:
        self._itr = 0
        self._data[:] = np.nan

    def finished(self):
        return self._itr == len(self._power_setup) and not np.isnan(self._data).any()

    def generate_generator_params(self) -> GeneratorParams | None:
        if self._waiting_for > 0:
            return None

        log.debug('Experiment step {}/{}: power {} ', 
                self._itr + 1, len(self._power_setup), self._power_setup[self._itr])

        params = deepcopy(Parameters().get().generator)
        if self._power_setup[self._itr] is None:
            params.connection.transmission_enabled = False
        else:
            params.connection.transmission_enabled = True
            params.connection.transmit_power = self._power_setup[self._itr]

        self._waiting_for = self._rx_count

        return params

    def store_results(self, device_id: str, results) -> None:
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
        self._waiting_for -= 1

        if self._waiting_for == 0:
            self._itr += 1

