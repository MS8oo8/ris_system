import zmq
import json
import numpy as np
import time
import sys

ON_WINDOWS = False

try:
    import uhd
except ImportError:
    ON_WINDOWS = False

if len(sys.argv) < 2:
    print("Użycie: python3 nazwa_pliku.py <numer_RX>")
    sys.exit(1)
rx_number = sys.argv[1] 
rx_name = f"RX_{rx_number}" 


address_push_f = "tcp://192.168.8.180:5562"  # PUSH do serwera
address_pull_f = "tcp://192.168.8.180:5563"
address_push = "tcp://192.168.8.180:5564"  # PUSH do serwera
address_pull = "tcp://192.168.8.180:5565"  # PULL od serwera

#print(ON_WINDOWS)
if ON_WINDOWS:
    #address_req = "tcp://localhost:5559"
    address_push_f = "tcp://localhost:5562"  # PUSH do serwera
    address_pull_f = "tcp://localhost:5563"
    address_push = "tcp://localhost:5564"
    address_pull = "tcp://localhost:5565"

context = zmq.Context()

socket_push_f = context.socket(zmq.PUSH)
socket_push_f.connect(address_push_f)

socket_pull_f = context.socket(zmq.PULL)
socket_pull_f.connect(address_pull_f)


socket_push = context.socket(zmq.PUSH)
socket_push.connect(address_push)

socket_pull = context.socket(zmq.PULL)
socket_pull.connect(address_pull)

#if ON_WINDOWS:
    #print(f"Symulacja połączenia z USRP dla {rx_name}")
#else:
usrp = uhd.usrp.MultiUSRP()

def configure_usrp(frequency, gain, sample_rate):
    if ON_WINDOWS:
        print(f"[{rx_name}] Ustawiono kanał RX2: frequency={frequency} Hz, gain={gain} dB, rate={sample_rate} S/s")
    else:
        usrp.set_rx_rate(sample_rate)
        usrp.set_rx_freq(frequency, 1)
        usrp.set_rx_gain(gain, 1)
        print(f"[{rx_name}] Ustawiono kanał RX2: frequency={frequency} Hz, gain={gain} dB, rate={sample_rate} S/s")
print("Czekam")
#time.sleep()
print(f"[{rx_name}] Wysyłam zgłoszenie gotowości do serwera...")
socket_push_f.send(json.dumps({
    "component": "rx", 
    "action": "ready_for_config", 
    "rx_name": rx_name
    }).encode("utf-8")) 
counter = 0
while True:
    try:
        config_data = json.loads(socket_pull.recv().decode("utf-8")) 
        print(f"[{rx_name}] Otrzymano wiadomość pull: {config_data}") 
        
        if config_data and config_data.get('frequency')  and config_data.get('gain'):
            frequency = config_data["frequency"]
            gain = config_data["gain"]
            sample_rate=1e6

            print(f"[{rx_name}] Wysyłanie konfiguracji do USRP")
            configure_usrp(frequency, gain,sample_rate)
            print(f"[{rx_name}] Skonfigurowano USRP")
        
        if config_data["action"] in "start_rx":
            print("dostałem action start_rx rozpoczynam pomiar")

            
            ris_id = config_data.get("ris_id", None)
            if counter == 27:
                counter = 1
            else:
                counter += 1
            
            buffer_size = config_data.get("buffer_size", None) #DVBT z gen
            N = config_data.get("N", None)

            power_measurements = []
            while len(power_measurements) < N:
                #samples = np.random.normal(0, 1, buffer_size) + 1j * np.random.normal(0, 1, buffer_size)
                samples = usrp.recv_num_samps(buffer_size,frequency,sample_rate, [0], gain)
                #print(buffer_size,frequency,sample_rate, [0], gain)
                power = np.mean(np.abs(samples) ** 2)
                power_measurements.append(float(power))

            socket_push.send(json.dumps({
                "component": "rx", 
                "action": "power_array", 
                "values": power_measurements, 
                "rx_name": rx_name,
                "ris_id": ris_id 
                }).encode("utf-8"))  
            print(f"[{rx_name}] Wysłano {N} pomiarów mocy do serwera. Dodano {counter}")

        
        
    except zmq.Again:
        pass

    except Exception as e:
        print(f"[{rx_name}] Błąd: {e}")
        time.sleep(1)

            

                