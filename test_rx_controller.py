import sys
import pytest
import numpy as np
from unittest.mock import MagicMock, patch

mock_uhd = MagicMock()
sys.modules['uhd'] = mock_uhd
sys.modules['uhd.usrp'] = mock_uhd.usrp

from controllers.rx_controller import RxController
from helpers.parameters import RxConfigChangeRequest

@pytest.fixture
def rx_ctrl():
    #tworzymy funkcję zastępczą dla konstruktora bazowego, która nada parametry zanim RxController spróbuje ich użyć
    def fake_base_init(self_instance, *args, **kwargs):
        self_instance._component_id = "0"
        self_instance._test_mode = False
        self_instance._parameters = MagicMock()
        self_instance._parameters.rx_initial_avg_power_history_dbm = -80.0
        self_instance._parameters.rx_log_history_coeff = 0.9

    with patch('controllers.rx_controller.Controller.__init__', fake_base_init):
        ctrl = RxController()
        ctrl._send_message = MagicMock()
        return ctrl
    

def test_on_message_new_ack_success(rx_ctrl):
    #sprawdzamy połączenie z USRP po otrzymaniu przydziału z głównego kontrolera
    message = {
        'action': 'new-ack',
        'data': {
            'usrp_serial': '31FA09B',
            'frequency_hz': 5e9, 'samp_rate': 1e6, 'gain_db': 40, 'buffer_size': 1024, 'repeats': 1
        }
    }
    
    rx_ctrl._on_message_received(message)
    
    mock_uhd.usrp.MultiUSRP.assert_called_with('serial=31FA09B')
    rx_ctrl._send_message.assert_called_once_with({'action': 'ready'})

@patch('subprocess.getoutput')
def test_on_message_new_ack_hardware_error(mock_getoutput, rx_ctrl):
    #weryfikujemy logikę diagnostyczną UHD po błędzie podłączenia
    mock_uhd.usrp.MultiUSRP.side_effect = Exception("No devices found")
    mock_getoutput.return_value = "Diagnostic UHD Dump"
    
    message = {
        'action': 'new-ack',
        'data': {'usrp_serial': 'BAD_SERIAL', 'frequency_hz': 5e9, 'samp_rate': 1e6, 'gain_db': 40, 'buffer_size': 1024, 'repeats': 1}
    }
    
    rx_ctrl._on_message_received(message)
    
    assert rx_ctrl._send_message.call_count == 2
    err_msg = rx_ctrl._send_message.call_args_list[0][0][0]
    assert err_msg['action'] == 'hardware-error'
    assert err_msg['found_devices'] == "Diagnostic UHD Dump"

def test_configure_rx(rx_ctrl):
    config_req = RxConfigChangeRequest(frequency_hz=5e9, samp_rate=1e6, gain_db=30, buffer_size=1024, repeats=2)
    rx_ctrl._configure_rx(config_req)
    assert rx_ctrl._frequency == 5e9
    assert rx_ctrl._N == 2

@patch('controllers.rx_controller.usrp')
def test_measure_math_logic(mock_global_usrp, rx_ctrl):
    rx_ctrl._N = 2
    fake_samples = np.array([0.1 + 0j, 0.0 + 0.1j, -0.1 + 0j])
    
    with patch.object(rx_ctrl, '_recv_samples_safe', return_value=fake_samples):
        measurements = rx_ctrl._measure({})
        assert len(measurements) == 2
        assert measurements[0] == -20.0