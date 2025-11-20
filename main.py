import sys
import time
from loguru import logger as log

from helpers.helpers import RestartRequired
from algorithms.algorithm import ExampleAlgorithm
from algorithms.experiment import ExampleExperiment
from controllers.launcher import create_controller
from helpers.parameters import Parameters

# 1. set log level
log.remove()
log.add(sys.stderr, level="INFO") 

# 2. set parameters
parameters = Parameters(
    frequency_hz=2.3e9,
    rx_count=1,
    test_mode=True
)

# 3. set algorithm
algorithm = ExampleAlgorithm(
    parameters=parameters,
    signal_power= [10.0, None, -5],
    pattern_ids=[0],
    results_dir="results" 
)

# 4. set experiment
experiment = ExampleExperiment(
    parameters=parameters,
    power_setup=[-30, -25, -20, None, -15] * 1000 ,
    results_dir="results" 
)


if __name__ == '__main__':
    # read input from command line
    controller_type = 'system'
    controller_id = 0
    if len(sys.argv) == 2:
        controller_type = sys.argv[1].strip().lower()
    elif len(sys.argv) == 3:
        controller_type = sys.argv[1].strip().lower()
        controller_id = int(sys.argv[2])    

    while True:
        # create controller
        controller = create_controller(
            controller_type=controller_type,
            controller_id=controller_id,
            parameters=parameters,
            algorithm=algorithm,
            experiment=experiment
        )
        
        # run controller
        try:
            controller.run()
            break
        except KeyboardInterrupt:
            log.warning("Keyboard interrupt received. Shutting down controller...")
            controller._broadcast_action("done")
            break
        except RestartRequired:
            log.info("Restarting {} controller...", controller_type)
            time.sleep(Parameters().sleep_after_restart_s)
