import zmq
from loguru import logger as log
# import time
import json
# from RsSmw import *
import re
import subprocess

import numpy as np
from typing import Dict, Callable, List, Tuple
from helpers.zmq_connection import ZmqClient
from controllers.controller import Controller
import time
from helpers.parameters import Params

usrp = None


class RxController(Controller):

    # ------------------------  NARZĘDZIA / USRP  ------------------------

    def _list_available_usrp_serials(self) -> Tuple[List[str], List[Dict]]:
        try:
            import uhd  # noqa: F401
            global usrp
            try:
                out = subprocess.check_output(["uhd_find_devices"], text=True)
                serials = re.findall(r"serial=(\w+)", out)
                print("Znaleziono seriale: ", serials)
                print(out)
            except Exception:
                pass
        except Exception:
            pass

    def _init_usrp_from_params(self) -> bool:
        """
        Ponowna inicjalizacja USRP tak jak przy starcie, do użycia przy resecie.
        """
        global usrp
        try:
            import uhd  # noqa: F401
            params = Params()
            usrp_args = params.get_usrp_args(self._component_id)
            usrp = uhd.usrp.MultiUSRP(usrp_args)
            self._usrp_usb_sn = params.usrp.serial_map.get(self._component_id)
            log.info("USRP zainicjalizowany ponownie.")
            return True
        except Exception as e:
            self._list_available_usrp_serials()
            log.error(f"Ponowna inicjalizacja USRP nieudana: {e}")
            usrp = None
            return False

    def _reset_usrp_with_backoff(self, reason: str) -> bool:
        """
        Miękki reset urządzenia z narastającym backoffem.
        """
        global usrp
        self._consecutive_failures += 1
        wait_s = min(2 ** (self._consecutive_failures - 1), 60)  # 1,2,4,8...60s
        log.warning(f"Resetuję USRP (powód: {reason}). Odczekam {wait_s}s")
        try:
            del usrp
        except Exception:
            pass
        time.sleep(wait_s)
        ok = self._init_usrp_from_params()
        if ok:
            self._consecutive_failures = 0
        return ok

    def _recv_samples_safe(self) -> np.ndarray:
        """
        Pobranie próbek z automatycznym wykryciem błędu i resetem USRP.
        """
        global usrp
        attempts = 0
        last_err = None
        while attempts < self._max_attempts_per_read:
            attempts += 1
            try:
                return usrp.recv_num_samps(
                    self._buffer_size,
                    self._frequency,
                    self._samp_rate,
                    [0],
                    self._rx_gain
                )
            except Exception as e:
                msg = str(e)
                last_err = msg
                log.error(f"recv_num_samps wyjątek (próba {attempts}/{self._max_attempts_per_read}): {msg}")

                # typowe, „naprawialne” przypadki z B210
                is_transient = any(s in msg for s in [
                    "LIBUSB_TRANSFER_OVERFLOW",
                    "transfer overflow",
                    "accum_timeout",
                    "timeout",
                    "safe-call"
                ])

                if is_transient:
                    # spróbuj resetu i ponów
                    if not self._reset_usrp_with_backoff(msg):
                        # jeśli reset się nie udał, kolejna pętla spróbuje znów po backoffie
                        continue
                else:
                    # nieznany/stały błąd – rzuć dalej
                    raise
        # po wyczerpaniu prób:
        raise RuntimeError(
            f"Nie udało się pobrać próbek po {self._max_attempts_per_read} próbach. "
            f"Ostatni błąd: {last_err}"
        )

    # ------------------------  LIFECYCLE  ------------------------

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._avg_power_history = -100.0
        self._log_history_coeff = 0.95

        self._frequency = None
        self._samp_rate = None
        self._rx_gain = None
        self._buffer_size = None  # 327680
        self._N = None  # 8
        self._usrp_usb_sn = None

        # parametry odpornościowe (NOWE)
        self._max_attempts_per_read = 5   # ile prób z resetem na jedno pobranie
        self._consecutive_failures = 0    # licznik kolejnych porażek (do backoffu)

        if self._test_mode:
            print(f"Symulacja połączenia z USRP")
        else:
            import uhd  # noqa: F401
            global usrp
            params = Params()
            try:
                usrp_args = params.get_usrp_args(self._component_id)
                try:
                    usrp = uhd.usrp.MultiUSRP(usrp_args)
                    print(f"Polaczylem sie z USRP o id {self._component_id}")
                except Exception:
                    self._list_available_usrp_serials()
                    print(f"Brak wpisu USRP dla komponenetu o id= '{self._component_id}'")
                self._usrp_usb_sn = params.usrp.serial_map.get(self._component_id)
            except Exception as e:
                print(f"Nie udalo sie zainicjalizowac USRP: {e}")
                usrp = None

    # ------------------------  KOMUNIKACJA  ------------------------

    def _on_message_received(self, message: Dict):
        match message['action']:
            case 'new-ack':
                config = message['data']
                self._configure_rx(config)
                self._send_message({'action': 'ready'})
            case 'measure':
                config = message['data']
                result = self._measure(config)
                self._send_message({'action': 'measure-ack', 'data': result})
            case _:
                log.warning('this action is not defined!')

    # ------------------------  KONFIGURACJA  ------------------------

    def _configure_rx(self, config: Dict):
        if self._test_mode:
            log.info('(TEST) RX {} configured', self._component_id)
            return

        if 'frequency' in config:
            self._frequency = config['frequency']

        if 'samp_rate' in config:
            self._samp_rate = config['samp_rate']

        if 'rx_gain' in config:
            self._rx_gain = config['rx_gain']

        if 'buffer_size' in config:
            self._buffer_size = config['buffer_size']

        if 'N' in config:  # gdzie w innym miejscu N zalezna jest od tego inijka 78
            self._N = config['N']

        if self._test_mode is False:
            log.info(
                f"RX Configured: Frequency = {self._frequency} Hz, "
                f"Gain = {self._rx_gain} dB, sample rate = {self._samp_rate} S/s"
            )

    # ------------------------  POMIAR  ------------------------

    def _measure(self, config: Dict) -> List[float]:
        if self._test_mode:
            result = -80 + np.random.rand() * 20
            self._avg_power_history = pow(10.0, self._avg_power_history / 10.0) * self._log_history_coeff
            self._avg_power_history += pow(10.0, result / 10.0) * (1.0 - self._log_history_coeff)
            self._avg_power_history = 10.0 * np.log10(self._avg_power_history)
            log.info(f"Avg: {self._avg_power_history:.2f} dBm; Current: {result:.2f} dBm")
            return [result]  # symulation

        power_measurements = []
        while len(power_measurements) < self._N:
            # BEZPIECZNY ODBIÓR (z resetem w razie błędu)
            samples = self._recv_samples_safe()

            power_lin = np.mean(np.abs(samples) ** 2)
            power_log = 10 * np.log10(max(power_lin, 1e-20))  # strażnik na wypadek 0
            power_measurements.append(float(power_log))

            self._avg_power_history = pow(10.0, self._avg_power_history / 10.0) * self._log_history_coeff
            self._avg_power_history += power_lin * (1.0 - self._log_history_coeff)
            self._avg_power_history = 10.0 * np.log10(self._avg_power_history)
            log.info(f"Avg: {self._avg_power_history:.2f} dBm; Current: {power_log:.2f} dBm")

        return power_measurements
