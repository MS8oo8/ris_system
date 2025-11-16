from controllers.system_controller import SystemController
from controllers.generator_controller import GeneratorController
from controllers.rx_controller import RxController
from controllers.ris_controller import RisController


def create_controller(
    controller_type: str, 
    controller_id: int,
    *,
    port_pub: int,
    port_pull: int,
    algorithm=None,
    experiment=None,
    system_address: str,
    test_mode: bool 
    ):
   

   
    if controller_type == 'system':
        return SystemController(
            port_pub=port_pub,
            port_pull=port_pull,
            algorithm=algorithm,
            experiment=experiment
        )
        
    if controller_type == "generator":
        return GeneratorController(
            component_name="generator",
            component_id=str(controller_id),
            controller_address=system_address,
            port_sub=port_pub,
            port_push=port_pull,
            test_mode=test_mode
        )
        
    if controller_type == 'rx':
        return RxController(
            component_name = 'rx',
            component_id = str(controller_id),
            controller_address = system_address,
            port_sub = port_pub,
            port_push = port_pull,
            test_mode = test_mode
        )
        
    if controller_type == "ris":
        return RisController(
            component_name="ris",
            component_id=str(controller_id),
            controller_address=system_address,
            port_sub=port_pub,
            port_push=port_pull,
            test_mode=test_mode
        )
        
    raise ValueError(f"Unknown controller type '{controller_type}'")