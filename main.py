import sys
from loguru import logger as log
from controllers.system_controller import SystemController
from controllers.generator_controller import GeneratorController
from controllers.rx_controller import RxController
from controllers.ris_controller import RisController
from algorithms.algorithm import ExampleAlgorithm
from algorithms.experiment import ExampleExperiment

SYSTEM_CONTROLLER_ADDRESS = 'localhost' #'192.168.8.219' #
PORT_PUB_SUB = 5558
PORT_PUSH_PULL = 5559
TEST_MODE = False

log.remove()
log.add(sys.stderr, level="DEBUG") 

if __name__ == '__main__':
    if len(sys.argv) == 1:
        log.info('Starting SystemController')
        controller = SystemController(
            port_pub=PORT_PUB_SUB,
            port_pull=PORT_PUSH_PULL,
            algorithm=ExampleAlgorithm(),
            experiment=ExampleExperiment()
        )
        controller.run()
    elif 2 <= len(sys.argv) <= 3:
        cmd = str(sys.argv[1])
        match cmd:
            case "generator":
                log.info('Starting GeneratorController')
                controller = GeneratorController(
                    component_name='generator',
                    component_id='0',
                    controller_address=SYSTEM_CONTROLLER_ADDRESS,
                    port_sub=PORT_PUB_SUB,
                    port_push=PORT_PUSH_PULL,
                    test_mode=True #TEST_MODE
                )
                controller.run()
            case "rx":
                assert len(sys.argv) == 3
                log.info('Starting RxController')
                controller = RxController(
                    component_name='rx',
                    component_id=sys.argv[2],
                    controller_address=SYSTEM_CONTROLLER_ADDRESS,
                    port_sub=PORT_PUB_SUB,
                    port_push=PORT_PUSH_PULL,
                    test_mode=TEST_MODE
                )
                controller.run()
            case "ris":
                import time
                time.sleep(10)
                assert len(sys.argv) == 3
                log.info('Starting RisController')
                controller = RisController(
                    component_name='ris',
                    component_id=sys.argv[2],
                    controller_address=SYSTEM_CONTROLLER_ADDRESS,
                    port_sub=PORT_PUB_SUB,
                    port_push=PORT_PUSH_PULL,
                    test_mode=TEST_MODE
                )
                controller.run()
    else:
        log.error('Unknown starting command')
