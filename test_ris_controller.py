import pytest
from unittest.mock import MagicMock, patch
from controllers.ris_controller import RisController

@pytest.fixture
def ris_ctrl():
    def fake_base_init(self_instance, *args, **kwargs):
        self_instance._component_id = "0"
        self_instance._test_mode = False

    with patch('controllers.ris_controller.Controller.__init__', fake_base_init):
        ctrl = RisController()
        ctrl._parameters = MagicMock()
        ctrl._parameters.ris_serial_timeout = 0.1
        ctrl._send_message = MagicMock() 
        return ctrl

@patch('controllers.ris_controller.Serial')
def test_on_message_new_ack_success(mock_serial_class, ris_ctrl):
    #sprawdzamy, czy po otrzymaniu konfiguracji z głównego kontrolera RIS nawiązuje połączenie
    message = {
        'action': 'new-ack',
        'data': {
            'serial_port': '/dev/my_ris',
            'baudrate': 115200,
            'timeout': 1.0
        }
    }
    
    ris_ctrl._on_message_received(message)
    
    #weryfikacja połączenia i odesłania 'ready'
    mock_serial_class.assert_called_once_with('/dev/my_ris', baudrate=115200, timeout=1.0)
    ris_ctrl._send_message.assert_called_once_with({'action': 'ready'})

@patch('controllers.ris_controller.glob.glob')
@patch('controllers.ris_controller.Serial')
def test_on_message_new_ack_hardware_error(mock_serial_class, mock_glob, ris_ctrl):
    #sprawdzamy reakcję na brak fizycznego połączenia kablem USB
    mock_serial_class.side_effect = Exception("Port not found")
    mock_glob.return_value = ['/dev/moj_ris_inne']
    
    message = {'action': 'new-ack', 'data': {'serial_port': '/dev/bad_port', 'baudrate': 115200, 'timeout': 1.0}}
    
    ris_ctrl._on_message_received(message)
    
    #skrypt powinien zraportować hardware-error i zażądać restartu
    assert ris_ctrl._send_message.call_count == 2
    assert ris_ctrl._send_message.call_args_list[0][0][0]['action'] == 'hardware-error'
    assert ris_ctrl._send_message.call_args_list[1][0][0]['action'] == 'restart'

@patch('controllers.ris_controller.Serial')
def test_set_pattern_success(mock_serial_class, ris_ctrl):
    mock_port = MagicMock()
    mock_port.readline.return_value = b"#OK\r\n" 
    ris_ctrl.ser = mock_port
    
    result = ris_ctrl._set_pattern(b"0xABCD")
    
    assert result is True
    mock_port.write.assert_called_once_with(b"!0xABCD\n")

@patch('controllers.ris_controller.Serial')
def test_set_pattern_timeout(mock_serial_class, ris_ctrl):
    mock_port = MagicMock()
    mock_port.readline.return_value = b"" 
    ris_ctrl.ser = mock_port
    
    result = ris_ctrl._set_pattern(b"0xFFFF")
    assert result is False