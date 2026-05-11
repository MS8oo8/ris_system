import pytest
from unittest.mock import MagicMock, patch
from controllers.system_controller import SystemController
from helpers.parameters import Parameters

@pytest.fixture

def mock_dependencies():
    params = MagicMock(spec=Parameters)
    
    #dodajemy zmienne portów, o które SystemController pyta przy starcie
    params.system_controller_port_pub_sub = 5558
    params.system_controller_port_push_pull = 5559
    
    algo = MagicMock()
    exp = MagicMock()
    return params, algo, exp

@pytest.fixture
@patch('controllers.system_controller.ZmqServer')
@patch('controllers.system_controller.SystemLogic')
def sys_ctrl(mock_system_logic_class, mock_zmq_class, mock_dependencies):
    params, algo, exp = mock_dependencies
    ctrl = SystemController(parameters=params, algorithm=algo, experiment=exp)
    ctrl._send_message = MagicMock()
    return ctrl

def test_handle_ris_new_sends_new_ack(sys_ctrl):
    #sprawdzane jest, czy główny kontroler poprawnie odpowiada węzłom RIS konfiguracją
    sys_ctrl._system_logic.rises.received_new.return_value = {'serial_port': '/dev/ttyUSB0', 'baudrate': 115200}
    
    incoming_msg = {'component': 'ris', 'id': '0', 'action': 'new', '_id': 'trace123'}
    sys_ctrl._handle_message_received(incoming_msg)
    
    sys_ctrl._system_logic.rises.received_new.assert_called_once_with(device_id='0', unique_id='trace123')
    
    #system musi odesłać new-ack z danymi z logiki
    sent_msg = sys_ctrl._send_message.call_args[0][0]
    assert sent_msg['action'] == 'new-ack'
    assert sent_msg['data']['serial_port'] == '/dev/ttyUSB0'

def test_handle_rx_ready_updates_logic(sys_ctrl):
    #sprawdzane jest, czy status ready z sieci aktualizuje stany maszyn w SystemLogic
    incoming_msg = {'component': 'rx', 'id': '0', 'action': 'ready'}
    sys_ctrl._handle_message_received(incoming_msg)
    
    sys_ctrl._system_logic.rxes.received_ready.assert_called_once_with(device_id='0')