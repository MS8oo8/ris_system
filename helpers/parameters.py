from helpers.singleton import SingletonMeta
from typing import Dict, Optional
from pydantic import BaseModel, Field
from enum import Enum
import os
import re
import numpy as np
import pandas as pd
from datetime import datetime
from loguru import logger as log
import zipfile


class GeneratorModel(str, Enum):
    #SMM100A = "SMM100A"
    SMBV100A = "SMBV100A"


class GeneratorConnection(BaseModel):
    mode: str = "wlan"  # "dvbt"
    generator_model: GeneratorModel = GeneratorModel.SMBV100A
    ip_address: str = ""
    transmit_power: float = -20.0
    transmission_enabled: bool =  True
    frequency: float = 5e9
    port: int = 5025
    connection_type: str = "SOCKET"

    model_config = {
        "arbitrary_types_allowed" : True
    }


class GeneratorParams(BaseModel):
    model: GeneratorModel
    connection: Optional[GeneratorConnection] = None

    def __init__(self, **data):
        super().__init__(**data)
        if not self.connection:
            ip_map = {
                #GeneratorModel.SMM100A: "192.168.8.30",
                GeneratorModel.SMBV100A: "192.168.8.30"
            }
            self.connection = GeneratorConnection(
                generator_model=self.model,
                ip_address=ip_map.get(self.model, "192.168.8.30")
            )
    model_config = {
        "arbitrary_types_allowed" : True
    }




class RxParams(BaseModel):
    samp_rate: float = 500e3 # 8e6
    rx_gain: float = 40.0
    #tutaj ustawiona ilość RXow
    count: int = 1
    buffer_size: int = int(40e3) #32768 #int(1e6) #1024
    N: int = 1


class RisParams(BaseModel):
    pattern: str = None
    index: int = None



class Params(BaseModel):
    frequency: float = 5e9
    generator: GeneratorParams = GeneratorParams(model = GeneratorModel.SMBV100A)
    rxes: RxParams = RxParams()
    rises: Dict[str, RisParams] = Field(default={
        '0': RisParams(),
        # '1': RisParams()
        
        
        
    })#'1': RisParams()



class Parameters(metaclass=SingletonMeta):

    def __init__(self):
        self.data = Params()
        self._ris_port_map = {}
        self._ris_available_ports = None # self._scan_usb_ports()

        # log przypisanych portów
        for ris_id in self.data.rises:
            try:
                port = self.get_ris_port(ris_id)
                log.info("RIS {} przypisany do portu: {}", ris_id, port)
            except RuntimeError as e:
                log.error("Błąd przypisania portu do RIS {}: {}", ris_id, e)

    def get(self):
        return self.data

    def get_ris_port(self, component_id: str) -> str:
        if component_id in self._ris_port_map:
            return self._ris_port_map[component_id]

        if not self._ris_available_ports:
            raise RuntimeError(f"Brak dostępnych portów dla RIS {component_id}")

        port = self._ris_available_ports.pop(0)
        self._ris_port_map[component_id] = port
        log.debug("Przypisano RIS {} do portu {}", component_id, port)
        return port

    def _scan_usb_ports(self):
        dev_list = os.listdir('/dev')
        usb_ports = [f"/dev/{d}" for d in dev_list if re.match(r"ttyUSB[0-9]+", d)]
        usb_ports.sort()
        return usb_ports

    def save_experyment_result_csv(self, data: np.ndarray) -> None:
        results_dir = "results"
        os.makedirs(results_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rx_count = data.shape[0]

        for rx in range(rx_count):
            filename = os.path.join(results_dir, f"experiment_result_rx_{rx}_{timestamp}.csv")
            df = pd.DataFrame(data[rx, :], columns=["Result"])
            # df.to_csv(filename, index=False)
            log.debug("Saved experiment results to {}", filename)

    def save_algorithm_results_to_csv(self, data: np.ndarray, configs: np.ndarray, signal_power: list) -> None:
        results_dir = "results"
        os.makedirs(results_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rx_count, config_count, power_count = data.shape

        for rx in range(rx_count):
            rows = []
            for c in range(config_count):
                pattern_ids = configs[c]
                for p in range(power_count):
                    power = signal_power[p]
                    mean_val = data[rx, c, p]

                    if np.isnan(mean_val):
                        continue

                    row = {
                        "Power": "Noise" if power is None else power,
                        "Result": mean_val
                    }

                    for ris_idx, pattern_id in enumerate(pattern_ids):
                        row[f"PatternRIS{ris_idx}"] = pattern_id

                    rows.append(row)

            df = pd.DataFrame(rows)
            filename = os.path.join(results_dir, f"algorithm_results_rx_{rx}_{timestamp}.csv")
            # df.to_csv(filename, index=False)
            log.debug("Saved algorithm results for RX {} to {}", rx, filename)

    def export_all_results_to_zip(self, zip_filename: str = None):
        results_dir = "results"
        if zip_filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_filename = f"results/results_{timestamp}.zip"

        with zipfile.ZipFile(zip_filename, 'w') as zipf:
            for root, _, files in os.walk(results_dir):
                for file in files:
                    if file.endswith(".csv"):
                        full_path = os.path.join(root, file)
                        zipf.write(full_path, arcname=file)

        log.info("Exported all CSVs to ZIP file: {}", zip_filename)

    def export_combined_excel(self, excel_filename: str = None):
        results_dir = "results"
        if excel_filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_filename = f"results/results_combined_{timestamp}.xlsx"

        with pd.ExcelWriter(excel_filename) as writer:
            for file in os.listdir(results_dir):
                if file.endswith(".csv") and ("rx_" in file or "rx" in file):
                    filepath = os.path.join(results_dir, file)
                    sheet_name = os.path.splitext(file)[0][:31]
                    df = pd.read_csv(filepath)
                    df.to_excel(writer, sheet_name=sheet_name, index=False)

        log.info("Exported combined Excel file: {}", excel_filename)




# class Parameters(metaclass = SingletonMeta):

#     def __init__(self):
#         self.data = Params()
#         self._ris_port_map = {}
#         self._ris_available_ports = self._scan_usb_ports()
#         # optional read from file

#     def get(self):
#         return self.data
    
#     def get_ris_port(self, component_id: str) -> str:
#         if component_id in self._ris_port_map:
#             return self._ris_port_map[component_id]
        
#         if not self._ris_available_ports:
#             raise RuntimeError("Brak dostepnych porstow szeregowych dla RIS")
        
#         port = self._ris_available_ports.pop(0)
#         self._ris_port_map[component_id] = port
#         return port
    
#     def _scan_usb_ports(self):
#         dev_list = os.listdir('/dev')
#         usb_ports = [f"/dev/{d}" for d in dev_list if re.match(r"ttyUSB[0-9]+",d)]
#         usb_ports.sort()
#         return usb_ports
    
#     def save_experyment_result_csv(self, data: np.ndarray) -> None:
#         results_dir = "results"
#         os.makedirs(results_dir, exist_ok = True)
        
#         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
#         rx_count = data.shape[0]
#         for rx in range (rx_count):
#             filename = os.path.join(results_dir, f"experiment_result_rx_ {rx}_{timestamp}.csv")
#             df = pd.DataFrame(data[rx, :], columns = ["Result"])
#             df.to_csv(filename, index = False)
#             log.info("Saved experiment results to {}", filename)

        
#     def save_algorithm_results_to_csv(self, data: np.ndarray, configs: np.ndarray, signal_power: list) -> None:
#         results_dir = "results"
#         os.makedirs(results_dir, exist_ok= True)
        
#         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#         rx_count, config_count, power_count = data.shape
        
        
#         for rx in range(rx_count):
#             rows = []
#             for c in range(config_count):
#                 pattern_ids = configs[c]
#                 for p in range(power_count):
#                     power = signal_power[p]
#                     mean_val = data[rx, c, p]
                    
#                     if np.isnan(mean_val):
#                         continue
                    
#                     row = {
#                         "Power" : "Noise" if power is None else power,
#                         "Result" : mean_val
#                     }
                    
#                     for ris_idx, pattern_id in enumerate(pattern_ids):
#                         row[f"PatternRIS{ris_idx}"] =  pattern_id
                        
#                     rows.append(row)
                    
#         df = pd.DataFrame(rows)
#         filename = os.path.join(results_dir, f"algorithm_results_rx_{rx}_{timestamp}.csv")
#         df.to_csv(filename, index = False)
#         log.info("Saved algorithm results for RX {} to {}", rx, filename)
        
# #export to xls i zip

