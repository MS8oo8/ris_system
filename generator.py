import zmq
import time
import json
from RsSmw import *

ON_WINDOWS = False

address_push = "tcp://192.168.8.180:5558"  # Adres PUSH dla wiadomości asynchronicznych
address_pull = "tcp://192.168.8.180:5559"

if ON_WINDOWS:
    address_push = "tcp://localhost:5558"  # do wysylania 
    address_pull = "tcp://localhost:5559" #do odbierania



context = zmq.Context()

socket_push = context.socket(zmq.PUSH) 
socket_push.connect(address_push)

socket_pull = context.socket(zmq.PULL)
socket_pull.connect(address_pull)


if ON_WINDOWS:
    print('Powiedzmy ze sie udalo')
else:
    try:
        with open("config.json") as config_f:
            RsSmw.assert_minimum_version('5.0.44')
            config = json.load(config_f)
            IP_ADDRESS_GENERATOR = config["IP_ADDRESS_GENERATOR"]
            PORT = config["PORT"]
            CONNECTION_TYPE = config["CONNECTION_TYPE"]
            resource = f'TCPIP::{IP_ADDRESS_GENERATOR}::{PORT}::{CONNECTION_TYPE}'
            try:
                print(f"[INFO] Łączenie z generatorem pod adresem: {resource}")
                generator = RsSmw(resource, True, True, "SelectVisa='socket'")
                print("[INFO] Połączono z generatorem.")
            except Exception as e:
                print(f"[ERROR] Błąd podczas nawiązywania połączenia: {e}")
                exit()
    except FileNotFoundError:
        print("Brak pliku konfiguracyjnego. Upewnij się, że istnieje plik config.json.")
        exit()


def configure_generator(frequency, gain):
    try:
        if ON_WINDOWS:
            print("[GENERATOR] Skonfigurowany")
        else:

            generator.source.bb.dm.set_state(True)
            generator.source.frequency.fixed.set_value(frequency)
            generator.source.power.level.immediate.set_amplitude(gain)
            generator.output.state.set_value(True) 
            print(f"[GENERATOR] Nadawanie sygnału rozpoczęte: Frequency = {frequency} Hz, Gain = {gain} dBm")
    except Exception as e:
        print(f"[GENERATOR ERROR] Nie można skonfigurować generatora: {e}")
        raise

def configure_noise():
    try:
        if ON_WINDOWS:
            print("[GENERATOR] szum")
        else:
            generator.output.state.set_value(False)  
            print("[GENERATOR] Generator ustawiony w trybie szumu.")
    except Exception as e:
        print(f"[GENERATOR ERROR] Nie można ustawić trybu szumu: {e}")
        raise

def stop_generator():
    try:
        if ON_WINDOWS:
            print("[GENERATOR] Generator został wyłączony.")
        else:
            generator.output.state.set_value(False)
            print("[GENERATOR] Generator został wyłączony.")
    except Exception as e:
        print(f"[GENERATOR ERROR] Nie można wyłączyć generatora: {e}")
        raise

def handle_messages():
    try:
        poller = zmq.Poller()
        poller.register(socket_pull, zmq.POLLIN)

        while True:
            events = dict(poller.poll(timeout=100))  # 100 ms timeout
            if socket_pull in events:
                message = socket_pull.recv().decode("utf-8")
                data = json.loads(message)
                print(f"[GENERATOR] Otrzymano wiadomość: {data}")

                action = data.get("action")
                
                if action == "now":
                    action = data.get("action")
                    frequency = data.get("frequency")
                    gain = data.get("gain")
                    configure_generator(frequency, gain)
                    socket_push.send(json.dumps({"component": "generator", "status": "configured"}).encode("utf-8"))
                    print("[GENERATOR] Generator pozostaje w stanie nadawania.")
                elif action == "noise":
                    configure_noise()
                    socket_push.send(json.dumps({"component": "generator", "status": "noise_mode"}).encode("utf-8"))

                elif action == "off":
                    stop_generator()
                    socket_push.send(json.dumps({"component": "generator", "status": "stopped"}).encode("utf-8"))

                else:
                    print(f"[GENERATOR] Nieznana akcja: {action}")

    except KeyboardInterrupt:
        print("\n[GENERATOR] Zatrzymano program.")
        stop_generator()
    except Exception as e:
        print(f"[GENERATOR ERROR] {e}")
        stop_generator()

if __name__ == "__main__":
    try:
        socket_push.send(json.dumps({"component": "generator", "action": "ready"}).encode("utf-8"))
        print("[GENERATOR] Generator gotowy do pracy.")
        handle_messages()
    except KeyboardInterrupt:
        print("\n[GENERATOR] Zatrzymano program.")
        stop_generator()
    except Exception as e:
        print(f"[GENERATOR ERROR] {e}")
        stop_generator()
