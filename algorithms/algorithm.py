from loguru import logger as log
from typing import Tuple, Dict
from helpers.parameters import Parameters, GeneratorParams, RisParams
import numpy as np
from copy import deepcopy
import os
import pandas as pd
from datetime import datetime


class Algorithm:
    def __init__(self):
        self._ris_count = len(Parameters().get().rises)
        self._rx_count = Parameters().get().rxes.count

    def data_collection_finished(self) -> bool:
        raise NotImplementedError

    def data_collection_request(self) -> Tuple[GeneratorParams, Dict[str, RisParams]] | None:
        raise NotImplementedError

    def algorithm_step(self) -> Dict[str, RisParams]:
        raise NotImplementedError

    def store_results(self, device_id: str, results) -> None:
        raise NotImplementedError

    def reset(self) -> None:
        raise NotImplementedError


class ExampleAlgorithm(Algorithm):

    def __init__(self):
        super().__init__()

        self.all_patterns = {
            0: "0x8000800080008000800080008000800080008000800080008000800080008000",
            1: "0x4000400040004000400040004000400040004000400040004000400040004000",
            2: "0x2000200020002000200020002000200020002000200020002000200020002000",

        } #patterny same paskki pojedyncze - pojedyncze o roznej długosci - bez przeprlatych (do 4 grubosci)
        self.signal_power = [10.0] * 3 #5.0, 10.0

        self._ris_count == 1
        self.configs = np.array(np.meshgrid(list(self.all_patterns.keys()), list(self.all_patterns.keys()))).T.reshape(-1, 2)

        self.data = np.nan * np.ones((self._rx_count, self.configs.shape[0], len(self.signal_power)))

        self.signal_power_itr = 0
        self.config_itr = 0

        self.waiting_for = 0

    def reset(self) -> None:
        self.data[:] = np.nan

    def data_collection_finished(self):
        return not np.isnan(self.data).any()
        print(f'[DATA CHECK] data_collectiuon_finished: {finished}, has NaNs: {np.isnan(self.data).sum()}')

    def data_collection_request(self) -> Tuple[GeneratorParams, Dict[str, RisParams]] | None:
        if self.waiting_for > 0: #bylo >
            return None

        log.info('Algorithm requesting data for power {} {}/{}, config {} {}/{}', 
                self.signal_power[self.signal_power_itr], self.signal_power_itr + 1, len(self.signal_power),
                self.configs[self.config_itr, :], self.config_itr + 1, self.configs.shape[0])

        generator_params = deepcopy(Parameters().get().generator)
        if self.signal_power[self.signal_power_itr] is None:
            generator_params.connection.transmission_enabled = False
        else:
            generator_params.connection.transmission_enabled = True
            generator_params.connection.transmit_power = self.signal_power[self.signal_power_itr]

        ris_params = deepcopy(Parameters().get().rises)
        for ris_id in ris_params:
            ris_params[ris_id].pattern = self.all_patterns[self.configs[self.config_itr, int(ris_id)]]

        self.waiting_for = self._rx_count
        return generator_params, ris_params

    # def store_results(self, device_id: str, results) -> None:
    #     self.waiting_for -= 1
    #     self.data[int(device_id), self.config_itr, self.signal_power_itr] = np.mean(results)

    #     if self.waiting_for == 0:
    #         if self.data_collection_finished():
    #             Parameters().save_algorithm_results_to_csv(self.data, self.configs, self.signal_power)
    #         self._next_data_collection_iteration()

    def store_results(self, device_id: str, results) -> None:
        rx_id = int(device_id)
        power = self.signal_power[self.signal_power_itr]
        config = self.configs[self.config_itr]
        mean_result = float(np.mean(results))

        # dopisz dane do pliku CSV
        timestamp = datetime.now().strftime("%Y%m%d")
        results_dir = "results"
        os.makedirs(results_dir, exist_ok=True)
        filename = os.path.join(results_dir, f"live_algorithm_rx_{rx_id}_{timestamp}.csv")

        row = {
            "Timestamp": datetime.now().isoformat(),
            "Power": "Noise" if power is None else power,
            "Result": mean_result
        }
        for ris_idx, pattern_id in enumerate(config):
            row[f"PatternRIS{ris_idx}"] = pattern_id

        df = pd.DataFrame([row])
        df.to_csv(filename, mode='a', header=not os.path.exists(filename), index=False)

        # nadal aktualizuj strukturę w pamięci, jeśli potrzebna
        self.data[rx_id, self.config_itr, self.signal_power_itr] = mean_result
        self.waiting_for -= 1

        if self.waiting_for == 0:
            if self.data_collection_finished():
                Parameters().save_algorithm_results_to_csv(self.data, self.configs, self.signal_power)
            self._next_data_collection_iteration()

    def _next_data_collection_iteration(self) -> None:
        self.config_itr += 1
        if self.config_itr == self.configs.shape[0]:
            self.config_itr = 0

            self.signal_power_itr += 1
            if self.signal_power_itr == len(self.signal_power):
                self.signal_power_itr = 0

    def algorithm_step(self) -> Dict[str, RisParams]:
        # SELECT BEST ? CHANGE / ETC.
        ris_params = deepcopy(Parameters().get().rises)
        for ris_id in ris_params:
            ris_params[ris_id].pattern = self.all_patterns[self.configs[self.config_itr, int(ris_id)]]
        return ris_params
