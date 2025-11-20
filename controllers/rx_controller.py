import re
import time
import subprocess
from typing import Dict, List, Tuple

import numpy as np
from loguru import logger as log

from helpers.helpers import RestartRequired
from controllers.controller import Controller


usrp = None  # global handler for USRP (one instance per process)
rx_streamer = None


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
            usrp = "TEST"
            return True

        try:
            import uhd

            serial = self._parameters.rx_usrp_serial_map.get(self._component_id)
            if serial is None:
                raise RuntimeError(f"No USRP serial for RX {self._component_id}")

            usrp = uhd.usrp.MultiUSRP(f"serial={serial}")
            log.info(f"USRP reinitialized successfully (ID={self._component_id}, serial={serial})")

            return True

        except Exception as e:
            self._list_available_usrp_serials()
            log.error(f"USRP reinitialization FAILED: {e}")
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
        log.warning(f"[RX {self._component_id}] Sent REINIT request — reason: {reason}")


    def _reset_usrp_with_backoff(self, reason: str) -> bool:
        global usrp

        if self._test_mode:
            log.info("(TEST) Ignoring USRP reset")
            return True

        self._consecutive_failures += 1
        wait_s = min((self._consecutive_failures - 1), 60)

        log.warning(f"[RX {self._component_id}] Resetting USRP (sleep {wait_s}s)... reason: {reason}")

        try:
            del usrp
        except:
            pass

        time.sleep(wait_s)

        ok = self._init_usrp_from_params()

        if ok:
            log.info(f"[RX {self._component_id}] USRP recovered.")
            self._awaiting_reconfig = True
            self._notify_reinit(reason)
        else:
            log.error(f"[RX {self._component_id}] USRP did NOT recover after reset.")

        return ok


    def _recv_samples_safe(self) -> np.ndarray:
        global usrp

        assert not self._test_mode, "Cannot receive samples in test mode."

        # if getattr(self, "_awaiting_reconfig", False):
        #     log.warning(f"[RX {self._component_id}] Awaiting configuration after REINIT.")
        #     return None  

        attempts = self._parameters.rx_max_attempts_per_read

        for attempt in range(1, attempts + 1):

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
                self._notify_reinit('')
                raise RestartRequired()
                msg = str(e)
                time.sleep(5)
                print(msg)
                log.error(f"[RX {self._component_id}] recv_num_samps ERROR "
                        f"(attempt {attempt}/{attempts}): {msg}")

                transient = any(s in msg for s in [
                    "LIBUSB_TRANSFER_OVERFLOW",
                    "LIBUSB_TRANSFER_ERROR",
                    "LIBUSB_ERROR_NO_DEVICE",
                    "transfer overflow",
                    "accum_timeout",
                    "timeout",
                    "safe-call"
                ])
                try:


                    import os
                    try:
                        os.system("uhd_image_loader --args='type=b200,reset'")
                    except RuntimeError:
                        print('HERE')

                    import uhd
                    serial = self._parameters.rx_usrp_serial_map[self._component_id]
                    
                    # stream_cmd = uhd.types.StreamCMD(uhd.types.StreamMode.stop_cont)
                    # rx_streamer.issue_stream_cmd(stream_cmd)
                    # rx_metadata = uhd.types.RXMetadata()
                    # recv_buffer = np.zeros(rx_streamer.get_max_num_samps(), dtype=np.complex64)
                    # while True:
                    #     samps = rx_streamer.recv(recv_buffer, rx_metadata)
                    #     print(len(samps))
                    #     if len(samps) == 0:
                    #         break


                    # print(id(usrp))
                    del usrp

                    usrp = uhd.usrp.MultiUSRP(f"serial={serial}")
                
                    samples = usrp.recv_num_samps(
                        self._buffer_size,
                        self._frequency,
                        self._samp_rate,
                        [0],
                        self._rx_gain
                    )

                    self._consecutive_failures = 0
                    return samples
                except:
                    self._notify_reinit('')
                    raise RestartRequired()

                # if transient:
                #     self._reset_usrp_with_backoff(msg)
                #     continue

                log.error(f"[RX {self._component_id}] Non-transient USRP error: {msg}")
                #self._notify_reinit(msg)
                #self._awaiting_reconfig = True
                return None




    # def simulate_error(self, msg="LIBUSB_TRANSFER_OVERFLOW"):
    #     """
    #     Manual simulation of overflow / timeout / usb error
    #     """
    #     log.error(f"[RX {self._component_id}] SIMULATED ERROR: {msg}")

    #     transient = any(s in msg for s in [
    #         "LIBUSB_TRANSFER_OVERFLOW",
    #         "LIBUSB_TRANSFER_ERROR",
    #         "LIBUSB_ERROR_NO_DEVICE",
    #         "transfer overflow",
    #         "accum_timeout",
    #         "timeout",
    #         "safe-call"
    #     ])

    #     if transient:
    #         self._reset_usrp_with_backoff(msg)
    #         return

    #     raise RuntimeError(msg)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._frequency = None
        self._samp_rate = None
        self._rx_gain = None
        self._buffer_size = None
        self._N = None

        self._awaiting_reconfig = False
        self._consecutive_failures = 0
        self._avg_power_history = -100.0  
        self._log_history_coeff = 0.95  


        if self._test_mode:
            log.info(f"(TEST MODE) Simulating USRP for RX {self._component_id}")
            self._init_usrp_from_params()
        else:
            global usrp
            import uhd
            try:
                serial = self._parameters.rx_usrp_serial_map[self._component_id]
                usrp = uhd.usrp.MultiUSRP(f"serial={serial}")
                
                log.info(f"[RX {self._component_id}] Connected to USRP")
            except Exception as ex:
                self._list_available_usrp_serials()
                log.error(f"[RX {self._component_id}] USRP init FAILED: {ex}")

    def _on_message_received(self, message: Dict):
        action = message["action"]

        if self._awaiting_reconfig and message["action"] == "measure":
            log.warning(f"[RX {self._component_id}] Ignoring measure request — awaiting reconfig")
            self._send_message({"action": "measure-ack", "data": []}) 
            return

        match action:
            case "new-ack":
                self._configure_rx(message["data"])
                self._send_message({"action": "ready"})

            case "configure":
                self._configure_rx(message["data"])
                self._send_message({"action": "configure-ack"})
                self._send_message({"action": "ready"})

            case "measure":
                log.info('I GOT MEASURE!!!')
                result = self._measure(message["data"])
                log.info("WYSYLAM")
                self._send_message({"action": "measure-ack", "data": result})

            case "reinit":
                self._init_usrp_from_params()

            case _:
                log.warning(f"[RX] Unknown action {action}")


    def _configure_rx(self, config: Dict):
        self._frequency = config.get("frequency", self._frequency)
        self._samp_rate = config.get("samp_rate", self._samp_rate)
        self._rx_gain = config.get("rx_gain", self._rx_gain)
        self._buffer_size = config.get("buffer_size", self._buffer_size)
        self._N = config.get("N", self._N)

        self._awaiting_reconfig = False

        log.info(
            f"RX configured: F={self._frequency}, "
            f"Gain={self._rx_gain}, SR={self._samp_rate}, Buf={self._buffer_size}, N={self._N}"
        )

    def _measure(self, config: Dict) -> List[float]:
        if self._test_mode:
            result = -80 + np.random.rand() * 20
            self._avg_power_history = pow(10.0, self._avg_power_history / 10.0) * self._log_history_coeff
            self._avg_power_history += pow(10.0, result / 10.0) * (1.0 - self._log_history_coeff)
            self._avg_power_history = 10.0 * np.log10(self._avg_power_history)
            log.info(f"Avg: {self._avg_power_history:.2f} dBm; Current: {result:.2f} dBm")
            # time.sleep(5)
            return [result]

        power_measurements = []

        while len(power_measurements) < self._N:

            samples = self._recv_samples_safe()

            if samples is None:
                log.warning(f"[RX {self._component_id}] Aborting measurement – samples=None (awaiting reconfig)")
                return []



            power_lin = np.mean(np.abs(samples)**2)
            power_log = 10 * np.log10(power_lin)
            power_measurements.append(float(power_log))

            self._avg_power_history = pow(10.0, self._avg_power_history / 10.0) * self._log_history_coeff
            self._avg_power_history += power_lin * (1.0 - self._log_history_coeff)
            self._avg_power_history = 10.0 * np.log10(self._avg_power_history)

            log.info(f"Avg: {self._avg_power_history:.2f} dBm; Current: {power_log:.2f} dBm")

        return power_measurements

