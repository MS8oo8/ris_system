from typing import Dict, Tuple
from pydantic import BaseModel, Field
from enum import Enum


''' Available generator models (integrated) '''
class GeneratorModel(str, Enum):
    SMM100A = 'SMM100A' 
    SMBV100A = 'SMBV100A' 


''' Helper structure for generator settings modification '''
class GeneratorConfigChangeRequest(BaseModel):
    frequency_hz: float
    transmit_power_dbm: float | None
    transmission_enabled: bool


''' Helper structure for RIS settings modification '''
class RisConfigChangeRequest(BaseModel):
    pattern_index: int
    pattern_hex: str


''' Helper structure for RX settings modification '''
class RxConfigChangeRequest(BaseModel):
    frequency_hz: float
    samp_rate: float
    gain_db: float
    buffer_size: int
    repeats: int
        

''' All parameters of the system '''
class Parameters(BaseModel):
    ''' general parameters '''
    frequency_hz: float = 5e9
    sleep_after_restart_s: float = 3.0
    test_mode: bool = True
    test_mode_rx_fail_chance: float = 0.0

    ''' system controller parameters '''
    system_controller_ip_address: str = 'localhost'
    system_controller_port_pub_sub: int = 5558
    system_controller_port_push_pull: int = 5559
    system_controller_wait_time_s: float = 10.0

    ''' generator parameters '''
    generator_transmit_power_dbm: float = -20.0
    generator_transmission_enabled: bool = True
    generator_ip_address: str = "192.168.8.30"
    generator_port: int = 5025
    generator_selected_model: GeneratorModel = GeneratorModel.SMBV100A

    ''' rx / usrp parameters '''
    rx_usrp_serial_map: Dict[str, str] = Field(default={
       '0': '3273ADC',
       '1': '3113F3B',
    })
    rx_samp_rate: float = 500e3
    rx_gain_db: float = 40.0
    rx_buffer_size: int = int(40e3) 
    rx_count: int = 1
    rx_repeats: int = 1  
    rx_initial_avg_power_history_dbm: float = -100.0
    rx_log_history_coeff: float = 0.95

    ''' ris parameters '''
    ris_serial_map: Dict[str, str] = Field(default={
        '0': '/dev/ttyUSB0',
        '1': '/dev/ttyUSB1',
        '2': '/dev/ttyUSB2',
        '3': '/dev/ttyUSB3',
    })
    ris_settings: Dict[str, Tuple[int, str]] = Field(default={
        '0': (None, None),
        '1': (None, None),
        '2': (None, None),
        '3': (None, None),
    })
    ris_count: int = 3
    ris_serial_boudrate: int = 115200
    ris_serial_timeout: float = 10.0
