import os
from datetime import datetime
from typing import Tuple, Dict

import numpy as np
import pandas as pd
from loguru import logger as log

from helpers.parameters import (
    Parameters, GeneratorConfigChangeRequest, RisConfigChangeRequest
)


class Algorithm:
    def __init__(self, parameters: Parameters):
        self._parameters = parameters
        self._ris_count = parameters.ris_count
        self._rx_count = parameters.rx_count

    def data_collection_finished(self) -> bool:
        raise NotImplementedError

    def data_collection_request(self) -> Tuple[GeneratorConfigChangeRequest, Dict[str, RisConfigChangeRequest]] | None:
        raise NotImplementedError

    def algorithm_step(self) -> Dict[str, RisConfigChangeRequest]:
        raise NotImplementedError

    def store_results(self, device_id: str, results) -> None:
        raise NotImplementedError

    def reset(self) -> None:
        raise NotImplementedError


class ExampleAlgorithm(Algorithm):

    def __init__(self,
                 parameters: Parameters,
                 signal_power: list = None,
                 pattern_ids: list[int] | None = None,
                 results_dir: str = "results"):
        super().__init__(parameters=parameters)

        self.all_patterns = {
            0: "0x8000800080008000800080008000800080008000800080008000800080008000",
            1: "0x4000400040004000400040004000400040004000400040004000400040004000",
            2: "0x2000200020002000200020002000200020002000200020002000200020002000",
            3: "0x1000100010001000100010001000100010001000100010001000100010001000",
            4: "0x0800080008000800080008000800080008000800080008000800080008000800",
            5: "0x0400040004000400040004000400040004000400040004000400040004000400",
            6: "0x0200020002000200020002000200020002000200020002000200020002000200",
            7: "0x0100010001000100010001000100010001000100010001000100010001000100",
            8: "0x0080008000800080008000800080008000800080008000800080008000800080",
            9: "0x0040004000400040004000400040004000400040004000400040004000400040",
            10: "0x0020002000200020002000200020002000200020002000200020002000200020",
            11: "0x0010001000100010001000100010001000100010001000100010001000100010",
            12: "0x0008000800080008000800080008000800080008000800080008000800080008",
            13: "0x0004000400040004000400040004000400040004000400040004000400040004",
            14: "0x0002000200020002000200020002000200020002000200020002000200020002",
            15: "0x0001000100010001000100010001000100010001000100010001000100010001",
            16: "0xC000C000C000C000C000C000C000C000C000C000C000C000C000C000C000C000",
            17: "0x6000600060006000600060006000600060006000600060006000600060006000",
            18: "0x3000300030003000300030003000300030003000300030003000300030003000",
            19: "0x1800180018001800180018001800180018001800180018001800180018001800",
            20: "0x0C000C000C000C000C000C000C000C000C000C000C000C000C000C000C000C00",
            21: "0x0600060006000600060006000600060006000600060006000600060006000600",
            22: "0x0300030003000300030003000300030003000300030003000300030003000300",
            23: "0x0180018001800180018001800180018001800180018001800180018001800180",
            24: "0x00C000C000C000C000C000C000C000C000C000C000C000C000C000C000C000C0",
            25: "0x0060006000600060006000600060006000600060006000600060006000600060",
            26: "0x0030003000300030003000300030003000300030003000300030003000300030",
            27: "0x0018001800180018001800180018001800180018001800180018001800180018",
            28: "0x000C000C000C000C000C000C000C000C000C000C000C000C000C000C000C000C",
            29: "0x0006000600060006000600060006000600060006000600060006000600060006",
            30: "0x0003000300030003000300030003000300030003000300030003000300030003",
        }

        self.signal_power = signal_power if signal_power is not None else [10.0]
        self._results_dir = results_dir

        if self._ris_count == 1:
            self.configs = np.array(list(self.all_patterns.keys()))
        elif self._ris_count == 2:
            self.configs = np.array(np.meshgrid(list(self.all_patterns.keys()), list(self.all_patterns.keys()))).T.reshape(-1, 2)
        else:
            assert False, 'Only 1 or 2 RIS supported'

        self.data = np.nan * np.ones((self._rx_count, self.configs.shape[0], len(self.signal_power)))

        self.signal_power_itr = 0
        self.config_itr = 0
        self.selected_config = None

        self.waiting_for = 0

        self.reset()

    def reset(self) -> None:
        self.data[:] = np.nan
        log.info("Searching best pattern...")

    def data_collection_finished(self):
        return not np.isnan(self.data).any()

    def data_collection_request(self) -> Tuple[GeneratorConfigChangeRequest, Dict[str, RisConfigChangeRequest]] | None:
        if self.waiting_for > 0: 
            return None

        generator_request = GeneratorConfigChangeRequest(
            frequency_hz=self._parameters.frequency_hz,
            transmit_power_dbm=self.signal_power[self.signal_power_itr],
            transmission_enabled=self.signal_power[self.signal_power_itr] is not None
        )

        ris_requests = { }
        if self._ris_count == 1:
            ris_requests['0'] = RisConfigChangeRequest(
                pattern_index=int(self.configs[self.config_itr]),
                pattern_hex=self.all_patterns[self.configs[self.config_itr]]
            )
        elif self._ris_count == 2:
            for ris_id in ['0', '1']: 
                ris_requests[ris_id] = RisConfigChangeRequest(
                    pattern_index=int(self.configs[self.config_itr, int(ris_id)]),
                    pattern_hex=self.all_patterns[self.configs[self.config_itr, int(ris_id)]]
                )
        else:
            assert False, 'Only 1 or 2 RIS supported'

        self.waiting_for = self._rx_count
        return generator_request, ris_requests


    def store_results(self, device_id: str, results) -> None:
        rx_id = int(device_id)
        power = self.signal_power[self.signal_power_itr]
        config = self.configs[self.config_itr]
        config = np.atleast_1d(config)
        mean_result = float(np.mean(results))


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

        self.data[rx_id, self.config_itr, self.signal_power_itr] = mean_result
        self.waiting_for -= 1

        if self.waiting_for == 0:
            self._next_data_collection_iteration()

        if self.data_collection_finished():
            self.selected_config = np.argmax(self.data, axis=1)[0][0]
            for i in range(len(self.configs)):
                log.info('Pattern {} avg. power: {} dBm {}', self.configs[i], self.data[0, i, 0], " --- selected " if i == self.selected_config else "")

    def _next_data_collection_iteration(self) -> None:
        self.config_itr += 1
        if self.config_itr == self.configs.shape[0]:
            self.config_itr = 0

            self.signal_power_itr += 1
            if self.signal_power_itr == len(self.signal_power):
                self.signal_power_itr = 0

    def algorithm_step(self) -> Dict[str, RisConfigChangeRequest]:
        ris_requests = { }
        if self._ris_count == 1:
            ris_requests['0'] = RisConfigChangeRequest(
                pattern_index=int(self.configs[self.selected_config]),
                pattern_hex=self.all_patterns[self.configs[self.selected_config]]
            )
        elif self._ris_count == 2:
            for ris_id in ['0', '1']:
                ris_requests[ris_id] = RisConfigChangeRequest(
                    pattern_index=int(self.configs[self.selected_config, int(ris_id)]),
                    pattern_hex=self.all_patterns[self.configs[self.config_itr, int(ris_id)]]
                )
        else:
            assert False, 'Only 1 or 2 RIS supported'
        return ris_requests
