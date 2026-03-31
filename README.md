ContRIS is an open-source framework for conducting synchronized measurement experiments with multiple Reconfigurable Intelligent Surfaces (RIS), multiple SDR receivers (e.g., USRP B210), and an external signal generator.
The system provides centralized scheduling, strict synchronization, and deterministic execution of experiments, eliminating the need for users to implement low-level device coordination or communication logic.

ContRIS is designed for RIS-based wireless communication and sensing experiments, where reliable synchronization across multiple devices is essential.

Requirements:
  - Python 3.8 or newer
  - Linux-based system (recommended)
  - Required Python packages listed in requirements.txt

Supported hardware:
  - Reconfigurable Intelligent Surfaces controllable via external interfaces
  - SDR receivers supported by the implemented SDR controller (e.g., USRP B210)
  - External RF signal generators supported by the implemented generator controller

Installation:

Clone the repository and install dependencies:
  - git clone https://github.com/MS8oo8/ris_system.git
  - cd ris_system
  - pip install -r requirements.txt

Basic Usage:

ContRIS consists of independent controllers that must be started separately.
Each controller registers itself with the main controller before any measurement can begin.

1. Start the main controller
   
python3 main.py

This command starts the main system controller, which waits for all required components to register.

2. Start SDR receiver controllers
Each SDR receiver is launched with a unique identifier:

python3 main.py rx 1
python3 main.py rx 2

If the system configuration specifies two receivers in helpers/parameters.py, the measurement process will not start until both receivers are running and have successfully registered.

3. Start RIS controllers
Each RIS unit is launched with its own identifier:

python3 main.py ris 1

Additional RIS units can be started in the same way using different IDs.

4. Start the signal generator controller
python3 main.py generator

Synchronization and execution logic
ContRIS enforces strict synchronization across all system components:
  The main controller waits until all expected devices (RIS units, SDR receivers, and the signal generator) have registered.
  The number of required receivers and RIS units is defined in helpers/parameters.py.
  Measurements begin only after all required components are active and ready.
  During an experiment, the system waits for measurement acknowledgments from all receivers before applying the next RIS configuration.
This guarantees that all recorded samples correspond to the same RIS pattern and experimental setup.

Configuration
All experiment and hardware parameters are defined in:

helpers/parameters.py

This file includes:
  - Number of SDR receivers
  - RIS configuration and identifiers
  - Signal generator parameters
  - Communication and timing settings

Experiment logic
User-defined experiment logic is implemented in:
algorithms/experiment.py
and/or
algorithms/algorithm.py

Users can modify or replace this file to implement custom measurement procedures or algorithms, while ContRIS handles synchronization, communication, and device control automatically.

License
This project is released under an open-source license.
See the LICENSE file for details.

Contact
For questions or support, please refer to the repository or contact the authors listed in the associated SoftwareX article.

Aha..
