import zmq
import json
import time
from unittest.mock import Mock

try:
    from serial import Serial
except ImportError:
    Serial = Mock()

ON_WINDOWS = False
address_push = "tcp://192.168.8.180:5561"  # Adres PUSH dla wiadomości asynchronicznych
address_pull = "tcp://192.168.8.180:5560"

if ON_WINDOWS:
    address_push = "tcp://localhost:5561"  # do wysylania 
    address_pull = "tcp://localhost:5560" #do odbierania

class MockSerial:
    """Symulowany port szeregowy dla RIS."""
    def __init__(self, port, baudrate=115200, timeout=10):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.buffer = []
        print(f"[MockSerial] Połączono z symulowanym portem {port}.")

    def flushInput(self):
        self.buffer = []

    def flushOutput(self):
        pass

    def write(self, data):
        print(f"[MockSerial] Odebrano dane do wysłania: {data}")
        self.buffer.append(data)

    def readline(self):
        if self.buffer:
            return b"#OK\n"  # Symulacja odpowiedzi #OK
        return b""  # Brak odpowiedzi


class RIS:
    def __init__(self, port, id=0, timeout=10, baudrate=115200):
        if ON_WINDOWS:
            self.ser = MockSerial(port, baudrate=baudrate, timeout=timeout)
        else:
            self.ser = Serial(port, baudrate=baudrate, timeout=timeout)
        self.ser.flushInput()
        self.ser.flushOutput()
        self.id = id
        self.timeout = timeout

    def set_pattern(self, pattern):
        """Ustawia wzorzec na RIS."""
        self.ser.flushInput()
        self.ser.flushOutput()
        self.ser.write(b"!" + pattern + b"\n")
        print(b"!" + pattern + b"\n")
        start_time = time.time()
        while True:
            response = self.ser.readline()
            print(response)
            if response.strip() == b"#OK":
                print(f"RIS: Wzorzec {pattern} ustawiony pomyślnie.")
                return True
            if time.time() - start_time > self.timeout:
                print("RIS: Timeout podczas ustawiania wzorca.")
                return False

with open("RIS_patterns.json") as pattern_file:
    patterns = json.load(pattern_file)["PATTERNS"]
pattern_map = {int(pattern["ID"]): pattern["HEX"] for pattern in patterns}


ris_device = RIS(port="/dev/ttyUSB0")  
ris_device.set_pattern(pattern_map[2].encode("utf-8"))
time.sleep(100)
context = zmq.Context()

socket_push = context.socket(zmq.PUSH)  # :5562
socket_push.connect(address_push)

socket_pull = context.socket(zmq.PULL)
socket_pull.connect(address_pull)

print("[RIS] Wysyłanie wiadomości gotowości do serwera.")
socket_push.send(json.dumps({"component": "ris", "action": "ready_ris"}).encode("utf-8"))

response = socket_pull.recv().decode("utf-8")
print(f"[RIS] Otrzymano odpowiedź od serwera: {response}")

with open("RIS_patterns.json") as pattern_file:
    patterns = json.load(pattern_file)["PATTERNS"]
pattern_map = {int(pattern["ID"]): pattern["HEX"] for pattern in patterns}

ris_device = RIS(port="/dev/ttyUSB0")

print("[RIS] Oczekiwanie na wiadomości od serwera...")

while True:
    try:
        message = json.loads(socket_pull.recv().decode("utf-8"))
        print(f"[RIS] Otrzymano wiadomość pull: {message}")

        if "action" not in message:
            print("[RIS] Wiadomość nie zawiera klucza 'action'.")
            continue    
        else:
            print("[RIS] Wiadomość zawiera klucz 'action'.")

        if message.get("component") == "ris" and message.get("action", "").startswith("put_pattern_"):
            try:
                id_pattern = int(message["action"].split("_")[-1])
                if id_pattern not in pattern_map:
                    print(f"[RIS] ID {id_pattern} nie istnieje w pliku RIS_patterns.json.")
                    continue

                hex_pattern = pattern_map[id_pattern].encode("utf-8")
                if ris_device.set_pattern(hex_pattern):
                    print(f"[RIS] Zmieniono wzorzec na ID {id_pattern}.")
                    socket_push.send(json.dumps({
                        "component": "ris",
                        "action": "pattern_update",
                        "pattern_id": id_pattern
                    }).encode("utf-8"))
                    print(f"[RIS] Wysłano informację o zmianie wzorca na ID {id_pattern}.")
            except ValueError:
                print("[RIS] Nieprawidłowy format ID w akcji.")
                continue

        else:
            print(f"[RIS] Nieznana akcja otrzymana od serwera. {message}")

    except zmq.error.ZMQError as e:
        print(f"[RIS] Błąd komunikacji z serwerem: {e}. Oczekiwanie na wiadomość ponownie...")
        time.sleep(1)
    except Exception as e:
        print(f"[RIS] Wystąpił nieoczekiwany błąd: {e}")
        time.sleep(1)
