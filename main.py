import sys
import time
from loguru import logger as log
import asyncio
import functools

from helpers.helpers import RestartRequired, Exit
from algorithms.algorithm import ExampleAlgorithm
from algorithms.experiment import ExampleExperiment
from controllers.launcher import create_controller
from helpers.parameters import Parameters

# 1. set log level
log.remove()
log.add(
    lambda msg: print(msg, end=''),
    colorize=True,
    format="<green>{time:HH:mm:ss}</green> | {level.name} | <cyan>{file}:{line}</cyan> - <level>{message}</level>",
    level="DEBUG"
)

# 2. set parameters
parameters = Parameters(
    frequency_hz=2.3e9,
    test_mode=True,
    ris_count=2
    # system_controller_ip_address = '192.168.8.219'
)

# 3. set algorithm
algorithm = ExampleAlgorithm(
    parameters=parameters,
    signal_power = ([10.0] * 1), # + [5.0] * 2 + [None] * 10),
    pattern_ids=[0],
    results_dir="../results" 
)

# 4. set experiment
experiment = ExampleExperiment(
    parameters=parameters,
    power_setup=([-30] * 10 + [None] * 10) ,
    results_dir="../results" 
)


def main(controller_type: str = None, controller_id: str = None):
    if controller_type is None and controller_id is None:
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
            controller._send_message({'action': "done"})
            break
        except Exit:
            break
        except RestartRequired:
            log.info("Restarting {} controller...", controller_type)
            time.sleep(Parameters().sleep_after_restart_s)

async def single_module(name: str, index: str):
    func = functools.partial(main, name, index)
    try:
        if name != 'system':
            await asyncio.sleep(3)
        await asyncio.to_thread(func)
    except Exception as e:
        print(e)
    

async def lanucher() -> None:
    tasks = [
        asyncio.create_task(single_module(name, cmd), name=name)
        for name, cmd in COMMANDS
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

COMMANDS = [
    ('system', None),
    ('generator', 0),
    ('ris', 0),
    ('ris', 1),
    ('rx', 0)
]

if __name__ == '__main__':
    # main()
    asyncio.run(lanucher())
