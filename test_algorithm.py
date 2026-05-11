import pytest
import numpy as np
from unittest.mock import MagicMock
from algorithms.algorithm import ExampleAlgorithm

@pytest.fixture
def mock_params():
    #tworzymy zamockowany obiekt parametrów
    params = MagicMock()
    params.ris_count = 2
    params.rx_count = 1
    params.frequency_hz = 5e9
    return params

def test_initialization_multi_ris(mock_params):
    #weryfikacja poprawności konfiguracji macierzy RISów
    mock_params.ris_count = 2
    algo = ExampleAlgorithm(parameters=mock_params)

    #patternów jest 32, risów 2, zatem macierz powinna mieć 64 rzędów
    assert algo.configs.shape == (64, 2)
    #weryfikacja czy RIS0 i RIS1 mają przypisane patterny w odpowiedniej kolejności
    assert algo.configs[0, 0] == 0  
    assert algo.configs[3, 1] == 0  

def test_data_collection_flow(mock_params):
    #test obiegu danych: request -> store -> next step
    mock_params.ris_count = 1
    mock_params.rx_count = 1
    algo = ExampleAlgorithm(parameters=mock_params, signal_power=[10.0])

    #pierwszy request
    gen_req, ris_reqs = algo.data_collection_request()
    assert gen_req.transmit_power_dbm == 10.0
    assert ris_reqs['0'].pattern_index == 0
    assert algo.waiting_for == 1

    #symulacja otrzymania wyniku
    algo.store_results("0", [ -55.0, -54.0 ]) 
    
    #po store_results dla rx_count=1, config_itr powinno skoczyć na 1
    assert algo.config_itr == 1
    assert algo.waiting_for == 0
    assert not np.isnan(algo.data[0, 0, 0])

def test_algorithm_finish_condition(mock_params):
    #sprawdzamy czy algorytm poprawnie wykrywa zakończenie zbierania danych
    mock_params.ris_count = 1
    mock_params.rx_count = 1
    algo = ExampleAlgorithm(parameters=mock_params, signal_power=[10.0])
    
    #mamy 3 wzorce w all_patterns. Musimy zapisać 3 wyniki.
    for i in range(32):
        algo.data_collection_request()
        algo.store_results("0", [ -60.0 ])

    assert algo.data_collection_finished() is True

    #sprawdzenie czy wybrano najlepszą konfigurację (argmax)
    assert algo.selected_config is not None

def test_waiting_for_logic(mock_params):
    #sprawdzamy czy algorytm blokuje requesty, gdy czeka na dane z wielu RX
    mock_params.rx_count = 2
    algo = ExampleAlgorithm(parameters=mock_params)
    
    algo.data_collection_request()
    assert algo.waiting_for == 2
    
    #kolejny request powinien być None, dopóki nie spłyną dane od obu RX
    assert algo.data_collection_request() is None
    
    algo.store_results("0", [-50])
    assert algo.waiting_for == 1
    assert algo.data_collection_request() is None 