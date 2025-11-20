import re
import time
import subprocess
from typing import Dict, List, Tuple

import numpy as np
from loguru import logger as log

from controllers.controller import Controller
from helpers.parameters import Parameters


usrp = None  # global handler for USRP (only one instance per controller / process)


class RxController(Controller):

    def _list_available_usrp_serials(self) -> List[str]:
        try:
            out = subprocess.check_output(["uhd_find_devices"], text=True)
            serials = re.findall(r"serial=([A-Za-z0-9]+)", out)
            log.warning(f"Available USRP devices: {serials}")
            return serials
        except Exception as e:
            log.warning(f"Could not execute uhd_find_devices: {e}")
            return []

    def _init_usrp_from_params(self) -> bool:
        global usrp

        if self._test_mode:
            log.info("(TEST) USRP init ok")
            usrp = "TEST USRP"
            return True

        try:
            import uhd

            serial = self._parameters.rx_usrp_serial_map.get(self._component_id)
            if serial is None:
                raise RuntimeError(f"No USRP serial found for RX ID {self._component_id}")

            usrp_args = f"serial={serial}"
            usrp = uhd.usrp.MultiUSRP(usrp_args)

            self._usrp_usb_sn = serial
            log.info(f"USRP reinitialized successfully (ID: {self._component_id}, serial={serial}).")
            return True

        except Exception as e:
            self._list_available_usrp_serials()
            log.error(f"USRP reinitialization failed: {e}")
            usrp = None
            return False

    def _notify_reinit(self, reason: str) -> None:
        payload = {
            'action': 'component-reinit',
            'component': 'rx',
            'id': self._component_id,
            'reason': reason,
            'need_config': True
        }

        self._send_message(payload)
        log.warning(f"[RX {self._component_id}] Sent reinit request (need_config=True). Reason: {reason}")

    def _reset_usrp_with_backoff(self, reason: str) -> bool:
        global usrp

        if self._test_mode:
            log.info("(TEST) Ignoring USRP reset (no hardware).")
            return True

        self._consecutive_failures += 1
        wait_s = min(2**(self._consecutive_failures - 1), 60)

        log.warning(f"[RX {self._component_id}] Resetting USRP due to: {reason}. Sleeping {wait_s}s...")

        try:
            del usrp
        except:
            pass

        time.sleep(wait_s)
        ok = self._init_usrp_from_params()

        if ok:
            log.info(f"[RX {self._component_id}] USRP recovered after reset.")
            self._consecutive_failures = 0

            # inform system that config is required
            self._awaiting_reconfig = True
            self._notify_reinit(reason)

        return ok

    def _recv_samples_safe(self) -> np.ndarray:
        global usrp
        assert self._test_mode is False, "Cannot receive samples in test mode."

        # MUST WAIT FOR CONFIG AFTER REINIT
        if getattr(self, "_awaiting_reconfig", False):
            log.warning(f"[RX {self._component_id}] Waiting for configuration after REINIT. Aborting measurement.")
            raise RuntimeError(f"[RX {self._component_id}] Awaiting reconfiguration")

        attempt = 0
        max_attempts = self._parameters.rx_max_attempts_per_read

        while attempt < max_attempts:
            attempt += 1
            try:
                samples = usrp.recv_num_samps(
                    self._buffer_size,
                    self._frequency,
                    self._samp_rate,
                    [0],
                    self._rx_gain
                )

                self._consecutive_failures = 0
                return samples

            except Exception as e:
                msg = str(e)
                log.error(
                    f"[RX {self._component_id}] recv_num_samps exception "
                    f"(attempt {attempt}/{max_attempts}): {msg}"
                )

                transient = any(s in msg for s in [
                    "LIBUSB_TRANSFER_OVERFLOW",
                    "LIBUSB_TRANSFER_ERROR",
                    "LIBUSB_ERROR_NO_DEVICE",
                    "transfer overflow",
                    "accum_timeout",
                    "timeout",
                    "safe-call"
                ])

                if transient:
                    self._reset_usrp_with_backoff(msg)
                    continue

                raise RuntimeError(f"[RX {self._component_id}] Fatal USRP error: {msg}")

        raise RuntimeError(f"[RX {self._component_id}] Failed to retrieve samples after {max_attempts} attempts.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._avg_power_history = self._parameters.rx_initial_avg_power_history_dbm
        self._log_history_coeff = self._parameters.rx_log_history_coeff

        self._frequency = None
        self._samp_rate = None
        self._rx_gain = None
        self._buffer_size = None
        self._N = None
        self._usrp_usb_sn = None

        self._consecutive_failures = 0
        self._awaiting_reconfig = False

        if self._test_mode:
            log.info(f"(TEST MODE) Simulating USRP for RX {self._component_id}")
            self._init_usrp_from_params()
        else:
            import uhd
            global usrp

            try:
                serial = self._parameters.rx_usrp_serial_map[self._component_id]
                usrp = uhd.usrp.MultiUSRP(f"serial={serial}")
                log.info(f"[RX {self._component_id}] Connected to USRP.")
            except KeyError:
                log.error(f"No USRP serial number found for RX ID '{self._component_id}'")
            except Exception as ex:
                self._list_available_usrp_serials()
                log.error(f"[RX {self._component_id}] Failed to initialize USRP: {ex}")

    def _on_message_received(self, message: Dict):
        action = message["action"]

        match action:
            case "new-ack":
                config = message["data"]
                self._configure_rx(config)
                self._send_message({"action": "ready"})

            case "configure":
                config = message["data"]
                self._configure_rx(config)
                self._send_message({"action": "configure-ack"})
                self._send_message({"action": "ready"})

            case "measure":
                config = message["data"]
                result = self._measure(config)
                self._send_message({"action": "measure-ack", "data": result})

            case "reinit":
                log.warning(f"[RX {self._component_id}] REINIT requested")

                if not self._test_mode:
                    ok = self._init_usrp_from_params()
                    if ok:
                        log.success(f"[RX {self._component_id}] USRP reinitialized successfully.")

            case "done":
                log.warning("[RX] Finish")

            case _:
                log.warning("Undefined RX action")

    def _configure_rx(self, config: Dict):
        if "frequency" in config:
            self._frequency = config["frequency"]

        if "samp_rate" in config:
            self._samp_rate = config["samp_rate"]

        if "rx_gain" in config:
            self._rx_gain = config["rx_gain"]

        if "buffer_size" in config:
            self._buffer_size = config["buffer_size"]

        if "N" in config:
            self._N = config["N"]

        # CONFIG RECEIVED → we are good to resume
        self._awaiting_reconfig = False

        log.info(
            f"RX Configured: Frequency = {self._frequency} Hz, "
            f"Gain = {self._rx_gain} dB, sample rate = {self._samp_rate} S/s"
        )

    def _measure(self, config: Dict) -> List[float]:
        if self._test_mode:
            result = -80 + np.random.rand() * 20
            self._avg_power_history = pow(10.0, self._avg_power_history / 10.0) * self._log_history_coeff
            self._avg_power_history += pow(10.0, result / 10.0) * (1.0 - self._log_history_coeff)
            self._avg_power_history = 10.0 * np.log10(self._avg_power_history)
            log.info(f"Avg: {self._avg_power_history:.2f} dBm; Current: {result:.2f} dBm")
            return [result]

        power_measurements = []

        while len(power_measurements) < self._N:
            samples = self._recv_samples_safe()
            power_lin = np.mean(np.abs(samples)**2)
            power_log = 10 * np.log10(power_lin)
            power_measurements.append(float(power_log))

            self._avg_power_history = pow(10.0, self._avg_power_history / 10.0) * self._log_history_coeff
            self._avg_power_history += power_lin * (1.0 - self._log_history_coeff)
            self._avg_power_history = 10.0 * np.log10(self._avg_power_history)

            log.info(f"Avg: {self._avg_power_history:.2f} dBm; Current: {power_log:.2f} dBm")

        return power_measurements
