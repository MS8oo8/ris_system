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


''' All parameters of the system '''
class Parameters(BaseModel):
    ''' general parameters '''
    frequency_hz: float = 5e9
    sleep_after_restart_s: float = 3.0
    test_mode: bool = False

    ''' system controller parameters '''
    system_controller_ip_address: str = '192.168.8.219' #'localhost'
    system_controller_port_pub_sub: int = 5558
    system_controller_port_push_pull: int = 5559

    ''' generator parameters '''
    generator_transmit_power_dbm: float = -20.0
    generator_transmission_enabled: bool = True
    generator_ip_address: str = "192.168.8.30"
    generator_port: int = 5025
    generator_selected_model: GeneratorModel = GeneratorModel.SMBV100A

    ''' rx / usrp parameters '''
    rx_usrp_serial_map: Dict[str, str] = Field(default={
       '0': '3273ADC',
       '1': '3273ACF',
    })
    rx_samp_rate: float = 500e3
    rx_gain_db: float = 40.0
    rx_buffer_size: int = int(40e3) 
    rx_count: int = 1
    rx_repeates: int = 1  
    rx_initial_avg_power_history_dbm: float = -100.0
    rx_log_history_coeff: float = 0.95
    rx_max_attempts_per_read: int = 5

    ''' ris parameters '''
    ris_serial_map: Dict[str, str] = Field(default={
        '0': '/dev/ttyUSB0',
        '1': '/dev/ttyUSB1',
    })
    ris_settings: Dict[str, Tuple[int, str]] = Field(default={
        '0': (None, None)
    })
    ris_count: int = 1
