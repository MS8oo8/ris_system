from helpers.singleton import SingletonMeta
from typing import Dict, Optional, List
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
 
class GeneratorSelect(BaseModel):
    selected: GeneratorModel = GeneratorModel.SMBV100A
    ip: Dict[GeneratorModel, str] = {
        GeneratorModel.SMBV100A: "192.168.8.30"
        
    }
    
_GEN = GeneratorSelect()

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
        sel_model = _GEN.selected
        super().__init__(model = sel_model, connection = data.get("connection"))
        
        # jeśli connection istnieje, ale puste IP → uzupełnij z _GEN
        if not self.connection.ip_address:
            self.connection.ip_address = _GEN.ip.get(self.model, "")

    model_config = {"arbitrary_types_allowed": True}



class RxParams(BaseModel):
    samp_rate: float = 1e6 # 8e6
    rx_gain: float = 40.0
    #tutaj ustawiona ilość RXow
    count: int = 1
    buffer_size: int = int(100e3) #32768 #int(1e6) #1024
    N: int = 1


class RisParams(BaseModel):
    pattern: str = None
    index: int = None


class ExperimentParams(BaseModel):
    power_setup: List[Optional[float]] = Field(
        default_factory=lambda: [-15] * 100
        #[None] * 100 + [10] * 50 + [None] * 100 + [10] * 50 + [None] * 100 + [10] * 50 + [None] * 100 + [10] * 50
    )
    
class AlgorithmParams(BaseModel):
    all_patterns: Dict[int, str] = Field(
        default_factory=lambda:{
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
            16: "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            17: "0x5555555555555555555555555555555555555555555555555555555555555555",
            18: "0xC000C000C000C000C000C000C000C000C000C000C000C000C000C000C000C000",
            19: "0x6000600060006000600060006000600060006000600060006000600060006000",
            20: "0x3000300030003000300030003000300030003000300030003000300030003000",
            21: "0x1800180018001800180018001800180018001800180018001800180018001800",
            22: "0x0C000C000C000C000C000C000C000C000C000C000C000C000C000C000C000C00",
            23: "0x0600060006000600060006000600060006000600060006000600060006000600",
            24: "0x0300030003000300030003000300030003000300030003000300030003000300",
            25: "0x0180018001800180018001800180018001800180018001800180018001800180",
            26: "0x00C000C000C000C000C000C000C000C000C000C000C000C000C000C000C000C0",
            27: "0x0060006000600060006000600060006000600060006000600060006000600060",
            28: "0x0030003000300030003000300030003000300030003000300030003000300030",
            29: "0x0018001800180018001800180018001800180018001800180018001800180018",
            30: "0x000C000C000C000C000C000C000C000C000C000C000C000C000C000C000C000C",
            31: "0x0006000600060006000600060006000600060006000600060006000600060006",
            32: "0x0003000300030003000300030003000300030003000300030003000300030003",
            33: "0xCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",
            34: "0x3333333333333333333333333333333333333333333333333333333333333333",
            35: "0xE000E000E000E000E000E000E000E000E000E000E000E000E000E000E000E000",
            36: "0x7000700070007000700070007000700070007000700070007000700070007000",
            37: "0x3800380038003800380038003800380038003800380038003800380038003800",
            38: "0x1C001C001C001C001C001C001C001C001C001C001C001C001C001C001C001C00",
            39: "0x0E000E000E000E000E000E000E000E000E000E000E000E000E000E000E000E00",
            40: "0x0700070007000700070007000700070007000700070007000700070007000700",
            41: "0x0380038003800380038003800380038003800380038003800380038003800380",
            42: "0x01C001C001C001C001C001C001C001C001C001C001C001C001C001C001C001C0",
            43: "0x00E000E000E000E000E000E000E000E000E000E000E000E000E000E000E000E0",
            44: "0x0070007000700070007000700070007000700070007000700070007000700070",
            45: "0x0038003800380038003800380038003800380038003800380038003800380038",
            46: "0x001C001C001C001C001C001C001C001C001C001C001C001C001C001C001C001C",
            47: "0x000E000E000E000E000E000E000E000E000E000E000E000E000E000E000E000E",
            48: "0x0007000700070007000700070007000700070007000700070007000700070007",
            49: "0xE38EE38EE38EE38EE38EE38EE38EE38EE38EE38EE38EE38EE38EE38EE38EE38E",
            50: "0x1C701C701C701C701C701C701C701C701C701C701C701C701C701C701C701C70",
            51: "0xF000F000F000F000F000F000F000F000F000F000F000F000F000F000F000F000",
            52: "0x7800780078007800780078007800780078007800780078007800780078007800",
            53: "0x3C003C003C003C003C003C003C003C003C003C003C003C003C003C003C003C00",
            54: "0x1E001E001E001E001E001E001E001E001E001E001E001E001E001E001E001E00",
            55: "0x0F000F000F000F000F000F000F000F000F000F000F000F000F000F000F000F00",
            56: "0x0780078007800780078007800780078007800780078007800780078007800780",
            57: "0x03C003C003C003C003C003C003C003C003C003C003C003C003C003C003C003C0",
            58: "0x01E001E001E001E001E001E001E001E001E001E001E001E001E001E001E001E0",
            59: "0x00F000F000F000F000F000F000F000F000F000F000F000F000F000F000F000F0",
            60: "0x0078007800780078007800780078007800780078007800780078007800780078",
            61: "0x003C003C003C003C003C003C003C003C003C003C003C003C003C003C003C003C",
            62: "0x001E001E001E001E001E001E001E001E001E001E001E001E001E001E001E001E",
            63: "0x000F000F000F000F000F000F000F000F000F000F000F000F000F000F000F000F",
            64: "0xF0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0",
            65: "0x0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F"
        }#patterny same paskki pojedyncze - pojedyncze o roznej długosci - bez przeprlatych (do 4 grubosci)
    )
    


class Params(BaseModel):
    frequency: float = 5e9
    generator: GeneratorParams = GeneratorParams(model = GeneratorModel.SMBV100A)
    rxes: RxParams = RxParams()
    rises: Dict[str, RisParams] = Field(default={
        '0': RisParams()

    })
    experiment: ExperimentParams = ExperimentParams()
    algorithm: AlgorithmParams = AlgorithmParams()                                 










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
            df.to_csv(filename, index=False)
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
            df.to_csv(filename, index=False)
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




