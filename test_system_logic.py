import pytest
from unittest.mock import MagicMock
from algorithms.system_logic import SystemLogic
from helpers.parameters import Parameters


@pytest.fixture
def logic():
    params = MagicMock(spec=Parameters)
    params.ris_count = 2
    params.rx_count = 1
    params.rx_usrp_serial_map = {'0': '31FA09B'}
    params.frequency_hz = 5e9
    params.rx_samp_rate = 500e3
    params.rx_gain_db = 40.0
    params.rx_buffer_size = 40000
    params.rx_repeats = 1
    
    algo = MagicMock()
    algo.data_collection_finished.return_value = False
    exp = MagicMock()
    
    return SystemLogic(parameters=params, algorithm=algo, experiment=exp)

def test_registration_flow(logic):
    #sprawdzanie poprawnego przechodzenia statusu gotowości przez DeviceHandlery
    logic.rxes.received_new(device_id='0', unique_id='uid1')
    logic.rxes.received_ready(device_id='0')
    assert logic.rxes.ready() is True
    
    #zarejestrowano RX, ale generator i RIS-y jeszcze nie są aktywne
    assert logic.ready() is False

def test_measurement_handling_phase_split(logic):
    #test podział na fazę algorytmiczną i ''eksperymentalną''
    fake_results = [-50.5]
    
    #faza 1: data_collection_phase = True
    logic.receive_measurement_results('0', fake_results)
    logic._algorithm.store_results.assert_called_once_with('0', fake_results)
    logic._experiment.store_results.assert_not_called()
    
    #ręcznie przestawiamy fazę
    logic._data_collection_phase = False
    
    #faza 2: data_collection_phase = False
    logic.receive_measurement_results('0', fake_results)
    logic._experiment.store_results.assert_called_once_with('0', fake_results)