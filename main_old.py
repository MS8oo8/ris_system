import zmq
import csv
import time
import json
import numpy as np
import datetime
import os
import sys
import pandas as pd
from collections import Counter


class SingletonMeta(type):
    _instances = {}
    
    def __call__(cls, *arg, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*arg, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]
    
class Algorithm(metaclass = SingletonMeta):
    def __init__(self):
        self.pattern_number = 27
        self.buffer_size = 32768
        self.N_signal = 8
        self.N_noise = 5 * self.N_signal
        self.gain_RX = 20
        self.frequency = 5E9
        self.ris_id_start = 1
        self.ris_id_end = 27
        self.gain = [-30, -29, -28, -27, -26, -25, -24, -23, -22, -21, -20, -19, -18, -17, -16, -15, -14, -13, -12, -11, -10, -9, -8, -7, -6, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  # Główna lista z wartościami gain
        self.ris_id_start = 1
        self.ris_id_end = 27
        self.patterns = {}  # Przechowywanie najlepszych wzorców dla RX
        self.results = {"RX_1": [], "RX_2": []}  # Wyniki pomiarów
        self.n_iterations = 1000  # Liczba iteracji dla sensing


    @property
    def gain_start(self):
        return self.gain[0]

    @property
    def gain_end(self):
        return self.gain[-1]

    @property
    def gain_step(self):
        if len(self.gain) > 1:
            return self.gain[1] - self.gain[0]
        return 0  # Domyślny krok, gdy jest tylko jedna wartość

    @property
    def number_of_gain(self):
        return len(self.gain)

class MeasurementSaver:
    def __init__(self):
        alg = Algorithm()
        self.ris_ids = list(range(alg.ris_id_start, alg.ris_id_end + 1))
        self.gain_values = list(range(alg.gain_start, alg.gain_end + 1, alg.gain_step))   
        self.row_headers = ["noise"] + [f"gain_{g}" for g in self.gain_values]
        self.data = self._initialize_table()
        self.generator_is_on = False 
        self.current_ris_ids = set()
        self.logger = CSVLogger("main_server_log.csv")

    def _initialize_table(self):
        rows = len(self.row_headers)
        cols = len(self.ris_ids) + 1 
        table = np.empty((rows + 1, cols), dtype=object)
        table[0, 1:] = self.ris_ids
        table[1:, 0] = self.row_headers
        return table

    def save_to_numpy(self, ris_id, power_measurements, generator, rx_name, suffix="original"):
       
        output_dir = "pomiarNPY"
        os.makedirs(output_dir, exist_ok=True)
       
        filename = os.path.join(output_dir,f"measurements_ris_{rx_name}_{suffix}.npy")
        
        if not os.path.exists(filename):
            #print(f"[INFO] Tworzenie nowego pliku dla {rx_name} z suffix '{suffix}': {filename}")
            self.data = self._initialize_table()
            np.save(filename, self.data)

        else:
            #print(f"[INFO] Wczytanie danych z istniejącego pliku dla {rx_name} z suffix '{suffix}': {filename}")
            self.data = np.load(filename, allow_pickle=True)

        if ris_id not in self.ris_ids:
            #print(f"[ERROR] Nieznany RIS_ID: {ris_id}")
            return

        ris_index = self.ris_ids.index(ris_id) + 1
        gain = generator.get_frequency_gain().get("gain", 0)

        if not generator.noise_completed:
            row_index = self.row_headers.index("noise") + 1
        else:
            row_index = self.row_headers.index(f"gain_{gain}") + 1

        if suffix == "original":
            self.data[row_index, ris_index] = power_measurements
        else:
            if isinstance(power_measurements, list):  # Jeśli dane to lista, weź pierwszą wartość
                self.data[row_index, ris_index] = power_measurements[0]
            else:
                self.data[row_index, ris_index] = power_measurements  

        self.current_ris_ids.add(ris_id)

        np.save(filename, self.data)
        #print(
        #    f"[INFO] Dane zapisane w pliku {filename}, kolumnie id_{ris_id}, wierszu {self.row_headers[row_index - 1]}."
        #)

    def print_table(self):
        
        print("Nagłówki kolumn:", self.data[0, 1:])
        print("Nagłówki wierszy:", self.row_headers)
        print("Dane pomiarowe:")
        print(self.data)
        


class MeasurementSaverCSV:
    def __init__(self):
        alg = Algorithm()
        self.ris_ids = list(range(alg.ris_id_start, alg.ris_id_end + 1))
        self.gain_values = list(range(alg.gain_start, alg.gain_end + 1, alg.gain_step))   
        self.row_headers = ["noise"] + [f"gain_{g}" for g in self.gain_values]
        self.data = self._initialize_table()
        self.generator_is_on = False
        self.current_ris_ids = set()
        self.logger = CSVLogger("main_server_log.csv")

    def _initialize_table(self):
        rows = len(self.row_headers)
        cols = len(self.ris_ids) + 1  
        table = np.empty((rows + 1, cols), dtype=object)
        table[0, 1:] = self.ris_ids
        table[1:, 0] = self.row_headers
        return table

    def save_to_csv(self, ris_id, power_measurements, generator, rx_name, suffix="original"):

        output_dir = "pomiarCSV"
        os.makedirs(output_dir, exist_ok=True)
        filename = os.path.join(output_dir, f"measurements_ris_{rx_name}_{suffix}.csv")

        if not os.path.isfile(filename):
            #print(f"[INFO] Tworzenie nowego pliku CSV dla {rx_name} z suffix '{suffix}': {filename}")
            self.data = self._initialize_table()
        else:
            #print(f"[INFO] Wczytywanie istniejących danych z pliku: {filename}")
            self.data = self._load_existing_csv(filename)

        if ris_id not in self.ris_ids:
            #print(f"[ERROR] Nieznany RIS_ID: {ris_id}")
            return

        ris_index = self.ris_ids.index(ris_id) + 1
        gain = generator.get_frequency_gain().get("gain", 0)

        if not generator.noise_completed:
            row_index = self.row_headers.index("noise") + 1
        else:
            row_index = self.row_headers.index(f"gain_{gain}") + 1

        if suffix == "original":
            self.data[row_index, ris_index] = power_measurements
        else:
            self.data[row_index, ris_index] = power_measurements[0] if isinstance(power_measurements, list) else power_measurements

        with open(filename, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([""] + self.ris_ids) 
            for row in self.data[1:]:
                writer.writerow(row)

        #print(f"[INFO] Dane zapisane do pliku CSV: {filename}")
        

    def _load_existing_csv(self, filename):
        
        table = self._initialize_table()
        with open(filename, "r", newline="") as csvfile:
            reader = csv.reader(csvfile)
            headers = next(reader)
            for i, row in enumerate(reader):
                table[i + 1] = row
        return table

    def print_table(self):
        """Wyświetla aktualną tablicę danych."""
        print("Nagłówki kolumn:", self.data[0, 1:])
        print("Nagłówki wierszy:", self.row_headers)
        print("Dane pomiarowe:")
        print(self.data)


#LOGI
class CSVLogger:
    def __init__(self, file_name):
        self.file_name = file_name
        with open(self.file_name, mode="a", newline="", encoding="utf-8") as log_file:
            writer = csv.writer(log_file)
            writer.writerow(["Timestamp", "Source", "Message"])

    def log(self, source, message):
        """Zapisuje wiadomość do pliku CSV z informacjami o czasie i źródle."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.file_name, mode="a", newline="", encoding="utf-8") as log_file:
            writer = csv.writer(log_file)
            writer.writerow([timestamp, source, message])


# Klasa RIS
class RIS:
    def __init__(self, ris_id, socket_push, socket_pull):
        self.ris_id = ris_id
        self.socket_push = socket_push
        self.socket_pull = socket_pull
        self.logger = CSVLogger("main_server_log.csv")

    def send_pattern_change(self):
        #print(f"[RIS] Wysyłanie żądania zmiany wzorca na ID {self.ris_id}.")
        try:
            self.socket_push.send(json.dumps({"component": "ris", "action": f"put_pattern_{self.ris_id}"}).encode('utf-8'))
            self.logger.log("RIS", f"zadanie zmiant wzorca ID {self.ris_id} zostalo wyslane")
        except zmq.ZMQError as e:
            self.logger.log("RIS", f"błąd podczas wysyłania żadania zmiany wzorca: {e}")
            return False

    def wait_for_pattern_update(self):
        #print("[RIS] Czekam na potwierdzenie zmiany wzorca...")
        poller = zmq.Poller()
        poller.register(self.socket_pull, zmq.POLLIN)

        start_time = time.time()
        while True:
            socks = dict(poller.poll(timeout=1000))
            if self.socket_pull in socks and socks[self.socket_pull] == zmq.POLLIN:
                try:
                    message = json.loads(self.socket_pull.recv().decode('utf-8'))
                    #self.logger.log("RIS", f"Otrzymano wiadomosc: {message}")
                    if message.get("action") == "pattern_update" and message.get("pattern_id") == self.ris_id:
                        #print(f"[RIS] Potwierdzono zmianę wzorca na ID {self.ris_id}.")
                        self.logger.log("RIS", f"Potwierdzono zmiane wzorca na ID {self.ris_id}")
                        return True
                except Exception as e:
                    self.logger.log("RIS", f"Blad podczas odbioru wiadomosci: {e}")
                    return False

            if time.time() - start_time > 10:
                #print("[RIS] Timeout podczas oczekiwania na potwierdzenie zmiany wzorca.")
                self.logger.log("RIS", f"Timeout podczas oczekiwania na potwierdzenie zmiany wzorca")
                return False
    
    def counter(self, ris_id):
        counter = ris_id
        self.logger.log("RIS",f"Counter {counter}")
        return counter

    def get_current_ris_id(self):
        return self.ris_id
        
    def increment_pattern_id(self):
        pattern_number = Algorithm().pattern_number
        self.ris_id = (self.ris_id % pattern_number) + 1
        self.logger.log("RIS", f"Zwiekszono ris_id: {self.ris_id}")



# Klasa RX
class RX:
    def __init__(self, port, socket_pull,socket_push, rx_name, generator,trace_file, fieldnames, ris,server):
        alg = Algorithm()
        self.port = port
        self.socket_pull = socket_pull
        self.socket_push = socket_push
        self.rx_name = rx_name  # Identyfikator RX
        self.gain = alg.gain_RX
        self.generator = generator 
        self.trace_file = trace_file  # Ścieżka do pliku CSV
        self.fieldnames = fieldnames  # Nagłówki pliku CSV
        self.ris = ris
        self.server = server
        self.logger = CSVLogger("main_server_log.csv")
        self.measurement_saver = MeasurementSaver()
        self.measurement_saverCSV = MeasurementSaverCSV()
        
        
    def send_ack_and_get_fg(self):
        #print(f"[{self.rx_name}] Wysyłanie żądania konfiguracji do serwera...")
        self.logger.log("RX", "Wysyłanie żądania konfiguracji do serwera...")

        try:
            response = {
                "frequency": self.generator.get_frequency_gain()["frequency"],
                "gain": self.gain
            }
            #print(f"[{self.rx_name}] Wysyłanie konfiguracji: {response}")
            self.logger.log("RX", f"Wysyłanie konfiguracji: {response}")

            self.socket_push.send(json.dumps(response).encode('utf-8'))
            #print(f"[{self.rx_name}] Wysłano konfigurację do serwera.")
            self.logger.log("RX", "Wysłano konfigurację do serwera.")

        except zmq.ZMQError as e:
            print(f"[{self.rx_name}] Błąd podczas komunikacji z serwerem: {e}")
            self.logger.log("RX", f"Błąd podczas komunikacji z serwerem: {e}")

            
    def start_next_measurement(self):
        """Rozpocznij kolejny pomiar po odebraniu sygnału 'ready_for_next'."""
        current_ris_id = self.ris.get_current_ris_id()
        try:
            self.logger.log("RX",f"[{self.rx_name}] Rozpoczynanie pomiaru...")
            self.socket_push.send(json.dumps({
                "component": "rx",
                "action": "start_rx",
                "rx_name": self.rx_name,
                "ris_id": current_ris_id,
                "buffer_size": Algorithm().buffer_size,
                "N": Algorithm().N_signal if self.generator.noise_completed else Algorithm().N_noise
            }).encode('utf-8'))
            self.logger.log("RX", f"[{self.rx_name}] Polecenie 'start_rx' wysłane do serwera.")
        except zmq.ZMQError as e:
            print(f"[{self.rx_name}] Błąd ZeroMQ: {e}")
            self.logger.log("RX", f"[{self.rx_name}] Blad ZeroMQ: {e}")
        except Exception as e:
            print(f"[{self.rx_name}] Nieoczekiwany błąd: {e}")
            self.logger.log("RX", f"[{self.rx_name}] Nieoczekiwany: {e}")
    
    def process_message(self, message, ris_id, rx_name):
        if message.get('component') == 'rx' and message.get('action') == "power_array":
            self.latest_measurements = message.get('values')
            
            # Zapis oryginalnych pomiarów
            self.measurement_saverCSV.save_to_csv(ris_id, self.latest_measurements, self.generator,rx_name, suffix="original")
            self.measurement_saver.save_to_numpy(ris_id, self.latest_measurements, self.generator, rx_name, suffix="original")
            
            # Obliczenie średniej wartości
            mean_value = self.calculate_mean(self.latest_measurements)
            self.measurement_saverCSV.save_to_csv(ris_id, [mean_value], self.generator,rx_name, suffix="mean")
            self.measurement_saver.save_to_numpy(ris_id, mean_value, self.generator, rx_name, suffix="mean")
            
            # Obliczenie odchylenia standardowego
            std_dev = self.calculate_std_deviation(self.latest_measurements)
            self.measurement_saverCSV.save_to_csv(ris_id, [std_dev], self.generator,rx_name, suffix="std_dev")
            self.measurement_saver.save_to_numpy(ris_id, std_dev, self.generator, rx_name, suffix="std_dev")
            
            # Obliczenie mocy w dBm
            power_dbm = self.calculate_power_dbm(mean_value)
            self.measurement_saverCSV.save_to_csv(ris_id, [power_dbm], self.generator,rx_name, suffix="power_dbm")
            self.measurement_saver.save_to_numpy(ris_id, power_dbm, self.generator, rx_name, suffix="power_dbm")
            
            self.logger.log("RX", f"[{rx_name}] Otrzymano i zapisano pomiary")
            return True
        else:
            self.logger.log("RX", f"[{rx_name}] Otrzymano nieoczekiwana wiadomosc: {message}")
            return False

    def calculate_mean(self,data_vector): 

        mean_value = np.mean(data_vector)
        #print(f"Średnia wartość: {mean_value}")
        return mean_value


    def calculate_std_deviation(self,data_vector):
        
        std_dev = np.std(data_vector)
        #print(f"Odchylenie standardowe: {std_dev}")
        return std_dev


    def calculate_power_dbm(self,mean_value, reference_impedance=50):

        if mean_value <= 0:
            raise ValueError("Średnia wartość napięcia musi być większa od zera.")
        
        power_watts = (mean_value ** 2) / reference_impedance 
        power_dbm = 10 * np.log10(power_watts / 1e-3) 
        #print(f"Moc w dBm: {power_dbm:.2f} dBm")
        return power_dbm
    
    
    def handle_power_array(self, message, ris_id,rx_name):
        """Obsługuje wiadomość dotyczącą pomiarów."""
        if not self.process_message(message, ris_id,rx_name):
            #print(f"[{self.rx_name}] Nie udało się przetworzyć wiadomości.")
            self.logger.log("RX", f"[{self.rx_name}] Nie udało sie przetworzyc wiaodmosci")


# Klasa Generator
class Generator:
    def __init__(self, ris_id):
        alg = Algorithm()
        self.is_on = False
        self.noise_completed = False
        self.frequency = alg.frequency
        self.gain = alg.gain_start
        self.max_gain = alg.gain_end
        self.ris = ris_id
        self.countid_ris = set()
        self.logger = CSVLogger("main_server_log.csv")


    def configure(self):

        user_action = "on" 
        if user_action == "on":
            self.is_on = True
            #print(f"[Generator] Generator został włączony z częstotliwością {self.frequency } GHz i zyskiem {self.gain} dB.")
            self.logger.log("Generator", f"Generator włączono z częstotliwością {self.frequency } GHz i zyskiem {self.gain} dB.")
            return {"action": "on"}
        else:
            #print("[Generator] Generator pozostaje wyłączony.")
            self.logger.log("Generator", "Generator pozostaje włączony.")
            return {"status": "idle"}

    def incriment_gain(self, is_on = None):
        
        if is_on is not None:
            self.is_on = is_on
        
        if self.is_on:
            step_gain = Algorithm().gain_step  
            if self.gain + step_gain <= self.max_gain:
                self.gain += step_gain
                #print(f"[Generator] Zwiększono gain do {self.gain} dB.")
                self.logger.log("Generator", f"Zwiększono gain do {self.gain} dB.")
            else:
                #print("[Generator] Nie można zwiększyć gain ponieważ jest on najwyższy.")
                self.logger.log("Generator", "Nie mozna zwiekszyc gain poniewaz jest najwyzszy.")
        return self.gain

    def get_frequency_gain(self):
        return {
            "frequency": self.frequency,
            "gain": self.gain,
            
        }
        
class Sensing:
    def __init__(self, output_dir="SensingResults"):
        alg = Algorithm()
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.logger = CSVLogger("main_server_log.csv")

    def find_best_pattern(self, file_rx1, file_rx2):

        def extract_best_pattern(file):
            #print("extract best 1")
            df = pd.read_csv(file)
            numeric_data = df.iloc[:,1:]
            best_patterns = []

            for index, row in numeric_data.iterrows():
                #print("w for w extract")
                max_value = row.max()
                #print("po max")
                best_pattern = row.idxmax()
                #print("idmax")
                best_patterns.append(best_pattern)

            most_common_pattern = Counter(best_patterns).most_common(1)[0][0]
            return most_common_pattern

        best_rx1 = extract_best_pattern(file_rx1)
        best_rx2 = extract_best_pattern(file_rx2)
        
        output_file = os.path.join(self.output_dir, "best_pattern_all.csv")
        with open(output_file, "w") as f:
            f.write("RX,Best Pattern\n")
            f.write(f"RX1,{best_rx1}\n")
            f.write(f"RX2,{best_rx2}\n")

        return best_rx1, best_rx2
    
    def find_best_pattern_v2(self, file_rx1, file_rx2):
        
        def extract_best_pattern(file):
            df = pd.read_csv(file)
            
            last_row = df.iloc[-1]
            
            numeric_data = pd.to_numeric(last_row[1:], errors='coerce')
            
            if numeric_data.isnull().all():
                print(f"no numeric data in {file}")
            
            max_value = numeric_data.max()
            
            best_pattern = numeric_data.idxmax()
            
            return best_pattern
        
        best_rx1 = extract_best_pattern(file_rx1)
        best_rx2 = extract_best_pattern(file_rx2)
        
        output_file = os.path.join(self.output_dir, "best_pattern_last.csv")
        with open(output_file, "w") as f:
            f.write("RX,Best Pattern\n")
            f.write(f"RX1,{best_rx1}\n")
            f.write(f"RX2,{best_rx2}\n")
        
                
        return best_rx1, best_rx2
        

    def check_measurement(self, socket_push_ris, socket_pull_ris, socket_push_generator, socket_pull_generator, socket_rx, best_rx1, best_rx2, scenarios):


        def set_ris_pattern(rx_name, pattern):
            #(f"[INFO] Ustawianie wzorca RIS dla {rx_name} na {pattern}.")
            self.logger.log("Sensing", f"Wysyłanie wzorca {pattern} do RIS dla {rx_name}")
            socket_push_ris.send(json.dumps({"component": "ris", "action": f"put_pattern_{pattern}"}).encode('utf-8'))
            
            while True:
                ris_response = json.loads(socket_pull_ris.recv().decode('utf-8'))
                #print(f"[DEBUG] Otrzymano odpowiedź RIS: {ris_response}")
                if (ris_response.get("component") == 'ris' and 
                    ris_response.get("action") == 'pattern_update'):
                    #and int(ris_response.get("pattern_id")) == pattern):
                    #print(f"[INFO] RIS pattern {pattern} potwierdzony dla {rx_name}.")
                    self.logger.log("Sensing", f"Potwierdzono wzorzec {pattern} dla {rx_name}")
                    break
                else:
                    print("[WARNING] Niepoprawna odpowiedź RIS, oczekiwanie kontynuowane.")

        def measure_rx(rx_name, pattern):
            #print(f"[INFO] Wysyłanie start_rx dla {rx_name} z wzorcem {pattern}.")
            self.logger.log("Sensing", f"Rozpoczęto pomiary dla {rx_name} z wzorcem {pattern}")
            #print(type(rx_name))


            socket_rx[rx_name]["push"].send(json.dumps({
                "component": "rx",
                "action": "start_rx",
                "rx_name": rx_name,
                "ris_id": pattern,
                "buffer_size": Algorithm().buffer_size,
                "N": Algorithm().N_signal #if self.generator.noise_completed else Algorithm().N_noise
            }).encode('utf-8'))

            while True:
                rx_response = json.loads(socket_rx[rx_name]["pull"].recv().decode('utf-8'))
                #print(f"[DEBUG] Otrzymano odpowiedź RX: {rx_response}")
                if (rx_response.get("component") == "rx" and 
                    rx_response.get("action") == "power_array" and 
                    rx_response.get("rx_name") == rx_name and 
                    rx_response.get("ris_id") == pattern):
                    power_values = rx_response.get("values")
                    average_power = np.mean(power_values)
                    std_dev_power = np.std(power_values)
                    average_power_dbm = 10 * np.log10(average_power)
                    #print(f"[INFO] Średnia moc: {average_power} W, {average_power_dbm} dBm, odchylenie standardowe: {std_dev_power}")
                    self.logger.log("Sensing", f"Średnia moc: {average_power} W, {average_power_dbm} dBm, odchylenie standardowe: {std_dev_power}")
                    return power_values, average_power, std_dev_power, average_power_dbm

        def send_generator_action(action, gain=None):
            #print(f"[INFO] Wysyłanie akcji {action} do generatora. Gain: {gain}")
            self.logger.log("Sensing", f"Wysyłanie akcji {action} do generatora z gain={gain}")

            if action == "noise":
                socket_push_generator.send(json.dumps({"action": "noise"}).encode('utf-8'))
                while True:
                    generator_response = json.loads(socket_pull_generator.recv().decode('utf-8'))
                    #print(f"[DEBUG] Otrzymano odpowiedź generatora: {generator_response}")
                    if (generator_response.get("component") == "generator" and 
                        generator_response.get("status") == "noise_mode"):
                        #print(f"[INFO] Generator nie nadaje.")
                        self.logger.log("Sensing", f"Generator nie nadaje")
                        break
                
                
            elif action == "now" and gain is not None:
                socket_push_generator.send(json.dumps({
                    "action": "now",
                    "frequency": 5E9,
                    "gain": gain
                }).encode('utf-8'))
            
                while True:
                    generator_response = json.loads(socket_pull_generator.recv().decode('utf-8'))
                    #print(f"[DEBUG] Otrzymano odpowiedź generatora: {generator_response}")
                    if (generator_response.get("component") == "generator" and 
                        generator_response.get("status") == "configured"):
                        #print(f"[INFO] Generator skonfigurowany z akcją {action} i gain={gain}.")
                        self.logger.log("Sensing", f"Generator skonfigurowany z akcją {action} i gain={gain}")
                        break

        for scenario_id, scenario in enumerate(scenarios, start=1):
            scenario_name = f"scenario_{scenario_id}"

            # Ścieżki do plików CSV dla RX_1 i RX_2 dla różnych danych
            output_rx1_original_csv = os.path.join(self.output_dir, f"{scenario_name}_RX_1_original.csv")
            output_rx1_mean_csv = os.path.join(self.output_dir, f"{scenario_name}_RX_1_mean.csv")
            output_rx1_std_csv = os.path.join(self.output_dir, f"{scenario_name}_RX_1_std.csv")
            output_rx1_dbm_csv = os.path.join(self.output_dir, f"{scenario_name}_RX_1_dBm.csv")

            output_rx2_original_csv = os.path.join(self.output_dir, f"{scenario_name}_RX_2_original.csv")
            output_rx2_mean_csv = os.path.join(self.output_dir, f"{scenario_name}_RX_2_mean.csv")
            output_rx2_std_csv = os.path.join(self.output_dir, f"{scenario_name}_RX_2_std.csv")
            output_rx2_dbm_csv = os.path.join(self.output_dir, f"{scenario_name}_RX_2_dBm.csv")

            #print(f"[INFO] Tworzenie plików CSV dla {scenario_name}")
            self.logger.log("Sensing", f"Stworzono pliki dla {scenario_name}")

            # Inicjalizacja struktur danych dla RX_1 i RX_2
            rx1_original_data = {"Scenario": [], "Vector": []}
            rx1_mean_data = {"Scenario": [], "Mean": []}
            rx1_std_data = {"Scenario": [], "Std": []}
            rx1_dbm_data = {"Scenario": [], "dBm": []}

            rx2_original_data = {"Scenario": [], "Vector": []}
            rx2_mean_data = {"Scenario": [], "Mean": []}
            rx2_std_data = {"Scenario": [], "Std": []}
            rx2_dbm_data = {"Scenario": [], "dBm": []}

            for gain in scenario:
                #(f"[INFO] Przetwarzanie wartości gain: {gain}")
                if gain is None: 
                    send_generator_action("noise")
                    self.logger.log("Sensing", "Wysłano noise do generatora")
                else: 
                    send_generator_action("now", gain)
                    self.logger.log("Sensing", f"Wysłano akcję now z gain={gain}")

                # Obsługa RX_1
                set_ris_pattern("RX_1", best_rx1)
                rx1_values, rx1_avg, rx1_std, rx1_avg_dbm = measure_rx("RX_1", best_rx1)
                rx1_original_data["Scenario"].append(gain)
                rx1_original_data["Vector"].append(rx1_values)
                rx1_mean_data["Scenario"].append(gain)
                rx1_mean_data["Mean"].append(rx1_avg)
                rx1_std_data["Scenario"].append(gain)
                rx1_std_data["Std"].append(rx1_std)
                rx1_dbm_data["Scenario"].append(gain)
                rx1_dbm_data["dBm"].append(rx1_avg_dbm)

                # Obsługa RX_2
                set_ris_pattern("RX_2", best_rx2)
                rx2_values, rx2_avg, rx2_std, rx2_avg_dbm = measure_rx("RX_2", best_rx2)
                rx2_original_data["Scenario"].append(gain)
                rx2_original_data["Vector"].append(rx2_values)
                rx2_mean_data["Scenario"].append(gain)
                rx2_mean_data["Mean"].append(rx2_avg)
                rx2_std_data["Scenario"].append(gain)
                rx2_std_data["Std"].append(rx2_std)
                rx2_dbm_data["Scenario"].append(gain)
                rx2_dbm_data["dBm"].append(rx2_avg_dbm)

                # Aktualizacja plików CSV dla RX_1
                pd.DataFrame(rx1_original_data).to_csv(output_rx1_original_csv, index=False)
                pd.DataFrame(rx1_mean_data).to_csv(output_rx1_mean_csv, index=False)
                pd.DataFrame(rx1_std_data).to_csv(output_rx1_std_csv, index=False)
                pd.DataFrame(rx1_dbm_data).to_csv(output_rx1_dbm_csv, index=False)

                # Aktualizacja plików CSV dla RX_2
                pd.DataFrame(rx2_original_data).to_csv(output_rx2_original_csv, index=False)
                pd.DataFrame(rx2_mean_data).to_csv(output_rx2_mean_csv, index=False)
                pd.DataFrame(rx2_std_data).to_csv(output_rx2_std_csv, index=False)
                pd.DataFrame(rx2_dbm_data).to_csv(output_rx2_dbm_csv, index=False)

                self.logger.log("Sensing", f"Zaktualizowano pliki dla {scenario_name}")

            #print(f"[INFO] Zakończono pomiary dla {scenario_name}.")






# Główna klasa serwera
class MainServer:
    def __init__(self):
        alg = Algorithm()
        self.sensing = Sensing()
        self.context = zmq.Context()
        
        self.pending_rx = set() 
        self.active_rx = set()  
        self.self_rxes = {}
        self.initialized_rx = set() 
        self.countid_ris = set()
        self.poller = zmq.Poller()
        self.logger = CSVLogger("main_server_log.csv")

        
        # PULL socket dla odbioru wiadomości od generatora
        self.socket_pull_generator = self.context.socket(zmq.PULL)
        self.socket_pull_generator.bind("tcp://*:5558")
        self.poller.register(self.socket_pull_generator, zmq.POLLIN)
        
        self.socket_push_generator = self.context.socket(zmq.PUSH)
        self.socket_push_generator.bind("tcp://*:5559")


        # PULL/PUSH dla RIS
        self.socket_pull_ris = self.context.socket(zmq.PULL)
        self.socket_pull_ris.bind("tcp://*:5561")
        self.poller.register(self.socket_pull_ris, zmq.POLLIN)

        self.socket_push_ris = self.context.socket(zmq.PUSH)
        self.socket_push_ris.bind("tcp://*:5560")
        
        # PULL socket do odbioru wiadomości od RX
        self.socket_pull = self.context.socket(zmq.PULL)
        self.socket_pull.bind("tcp://*:5562")
        self.poller.register(self.socket_pull, zmq.POLLIN)

        # PUSH socket do wysyłania odpowiedzi do RX
        self.socket_push = self.context.socket(zmq.PUSH)
        self.socket_push.bind("tcp://*:5563")##
        


        # RX Socket Mapping
        self.rx_sockets = {
            "RX_1": {
                "pull": self.context.socket(zmq.PULL),
                "push": self.context.socket(zmq.PUSH)
            },
            "RX_2": {
                "pull": self.context.socket(zmq.PULL),
                "push": self.context.socket(zmq.PUSH)
            },
        }
        self.rx_sockets["RX_1"]["pull"].bind("tcp://*:5564")
        self.rx_sockets["RX_1"]["push"].bind("tcp://*:5565")
        self.poller.register(self.rx_sockets["RX_1"]["pull"], zmq.POLLIN)
        
        self.rx_sockets["RX_2"]["pull"].bind("tcp://*:5566")##
        self.rx_sockets["RX_2"]["push"].bind("tcp://*:5567")
        self.poller.register(self.rx_sockets["RX_2"]["pull"], zmq.POLLIN)

        self.fieldnames = ["RIS_ID"]  
        self.trace_file = "trace_file.csv"
        
        # Inicjalizacja komponentów
        self.ris = RIS(
            ris_id=alg.ris_id_start,
            socket_push=self.socket_push_ris,
            socket_pull=self.socket_pull_ris
        )
        self.generator = Generator( ris_id=self.ris.ris_id)

        self.rx_instances = {}
        self.add_rx("RX_1")
        self.add_rx("RX_2")
        
        with open(self.trace_file, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
            writer.writeheader()
        

    
    def add_rx(self, rx_name):
        """Dodaj nowy RX do systemu"""
        
        rx = RX(
            port=self.rx_sockets[rx_name]["push"],
            socket_pull=self.rx_sockets[rx_name]["pull"],
            socket_push=self.rx_sockets[rx_name]["push"],
            rx_name=rx_name,
            generator=self.generator,
            trace_file=self.trace_file,
            fieldnames=self.fieldnames,
            ris = self.ris,
            #ris_id=self.ris.ris_id, 
            server=self
        )
        self.rx_instances[rx_name] = rx
        self.fieldnames.append(f"Power_{rx_name}")
        self.active_rx.add(rx_name)
        self.self_rxes[rx_name] = {"initialized": False, "pending": False, "completed": False, "all_done": False}
        self.logger.log("MainServer", f"Dodano RX: {rx_name}")
        
        

        
    def change_gen_gain(self, count):
        target_count = Algorithm().ris_id_end
        if not hasattr(self, '_counter'):
            self._counter = 0  
        if not hasattr(self, '_noise_measured'):
            self._noise_measured = False  

        required_set = set(range(1, target_count + 1))

        # Liczenie pomiarów dla noise (generator wyłączony)
        if not self._noise_measured:
            self._counter = len(count) 
            #print(f"[MainServer] Noise: {self._counter}/{target_count}. Generator nieaktywny.")
            self.logger.log("MainServer", f"Noise: {self._counter}/{target_count}. Generator nieaktywny.")

            if self._counter >= target_count:  # Dopiero przy pełnych danych noise
                #print("[MainServer] Noise zmierzony. Przygotowanie generatora...")
                self.logger.log("MainServer", "Noise zmierzony. Przygotowanie generatora.")
                
                self._noise_measured = True  # Noise został zmierzony
                return 

        if self._noise_measured and not self.generator.noise_completed:
            self.generator.noise_completed = True
            self.generator.is_on = True
            message = {
                      "action": "now",
                      "frequency": self.generator.get_frequency_gain()["frequency"],
                      "gain": self.generator.get_frequency_gain()["gain"]
                       }
            self.socket_push_generator.send(json.dumps(message).encode('utf-8')) 
            self.logger.log(f"ManSercer", "Generator wyslal wiadomosc {message}")           
            #print(f"[MainServer] Generator gotowy. Zaczynam pomiary z gain={self.generator.gain}. Wyslano akcje now")
            self.logger.log(f"MainServer", "Generator gotowy. Zaczynam pomiary z gain= {self.generator.gain}.")
            while True:
                received_message = self.socket_pull_generator.recv_json()
                self.logger.log("MainServer", f"Otrzymano wiadomość od generatora: {received_message}")
                if (received_message.get("component") == "generator" and 
                    received_message.get("status") == "configured"):
                    #print("[MainServer] Otrzymano potwierdzenie 'configured' od generatora1.")
                    self.logger.log("MainServer", "Otrzymano potwierdzenie 'configured' od generatora.")
                    break  
            
            
            self._counter = 1 
            self.countid_ris.clear()

            return

        self._counter = (len(count) + 1 )
        gain = self.generator.get_frequency_gain().get("gain", 0)
        #print(f"[MainServer] Gain={gain}: {self._counter}/{target_count}.")
        self.logger.log("MainServer", f"Gain={gain}: {self._counter}/{target_count}.")

        if required_set.issubset(count): 
            #print(f"[MainServer] Zebrano pełny zestaw dla gain={gain}.")
            self.logger.log("MainServer", f"Zebrano pełny zestaw dla gain={gain}.")
            
            if gain == Algorithm().gain_end and self._counter >= target_count:  
                #all_done = all(self.check_full_data(rx_name) for rx_name in self.self_rxes)
                #if all_done:
                for rx_name in self.self_rxes:
                    self.self_rxes[rx_name]["all_done"] = True
                #print("[MainServer] Wszystkie RX zakończyły swoje pomiary. Kończę program.")
                self.logger.log("MainServer", "Wszystkie RX zakończyły swoje pomiary. Kończę program.")
                self.socket_push_generator.send(json.dumps({"action": "off"}).encode('utf-8'))
                #Koniec pierwszego
                while True:
                    generator_response = json.loads(self.socket_pull_generator.recv().decode('utf-8'))
                    if (generator_response.get("component") == "generator" and 
                        generator_response.get("status") == "stopped"):
                        self.logger.log("MainServer", "Generator successfully stopped")
                        #print("[INFO] Generator successfully stopped.")
                        break
                self.logger.log("MainServer", "Wchodze do next_step")
                self.next_step()
                self.finish_program()
                return

            self.generator.incriment_gain(is_on=True)
            #print("[MainServer] Gain został zwiększony.")
            self.logger.log("MainServer", "Gain został zwiększony.")
            message = {
                      "action": "now",
                      "frequency": self.generator.get_frequency_gain()["frequency"],
                      "gain": self.generator.get_frequency_gain()["gain"]
                       }

            self.socket_push_generator.send(json.dumps(message).encode('utf-8'))

            #self.socket_push_generator.send(json.dumps({"action": "now"}).encode('utf-8'))
            #self.socket_push_generator.send(json.dumps(self.generator.get_frequency_gain()).encode('utf-8'))
            #print(f"[MainServer] Wysłano aktualne ustawienia dla gain={self.generator.gain}.")
            self.logger.log("MainServer", f"Wysłano aktualne ustawienia dla gain={self.generator.gain}.")
            while True:
                received_message = self.socket_pull_generator.recv_json()
                self.logger.log("MainServer", f"Otrzymano wiadomość od generatora: {received_message}")
                if (received_message.get("component") == "generator" and 
                    received_message.get("status") == "configured"):
                    #print("[MainServer] Otrzymano potwierdzenie 'configured' od generatora.")
                    self.logger.log("MainServer", "Otrzymano potwierdzenie 'configured' od generatora.")
                    break 
            self._counter = 0
            self.countid_ris.clear()
            
            
    def next_step(self):
        print("next+_step")
        best_rx1, best_rx2 = self.perform_best_pattern_analysis()
        print(best_rx1, best_rx2)
        brx1, brx2 = self.perfom_best_pattern_as_last()
        
        #scenerio_1 = [None] * 2 + [10] * 5 + [15] * 15
        #scenerio_2 = [None] * 3 + [-4] * 3 + [20] * 4
        
        scenerio_1 = [None] * 500 + [-18] * 500
        scenerio_2 = [None] * 500 + [-17] * 500
        scenerio_3 = [None] * 500 + [-16] * 500
        scenerio_4 = [None] * 500 + [-15] * 500
        scenerio_5 = [None] * 500 + [-14] * 500
        scenerio_6 = [None] * 500 + [-13] * 500
        scenerio_7 = [None] * 500 + [-12] * 500
        scenerio_8 = [None] * 1000 + [-30] * 100 + [-29] * 100 + [-28] * 100 + [-27] * 100 + [-26] * 100 + [-25] * 100 + [-24] * 100 + [-23] * 100 + [-22] * 100 + [-21] * 100 + [-20] * 100 + [-19] * 100 + [-18] * 100 + [-17] * 100 + [-16] * 100 + [-15] * 100 + [-14] * 100 + [-13] * 100 + [-12] * 100 + [-11] * 100 + [-10] * 100 + [-9] * 100 + [-8] * 100 + [-7] * 100 + [-6] * 100 + [-5] * 100 + [-4] * 100 + [-3] * 100 + [-2] * 100 + [-1] * 100 + [0] * 100 + [1] * 100 + [2] * 100 + [3] * 100 + [4] * 100 + [5] * 100 + [6] * 100 + [7] * 100 + [8] * 100 + [9] * 100 + [10] * 100
        scenerio_9 = [None] * 1000 + [-30] * 100 + [-15] * 100 + [-10] * 100 + [-5] * 100 + [0] * 100 + [5] * 100 + [10] * 100
        scenerio_10 = [None] * 500 + [-26] * 500
        scenerio_11 = [None] * 500 + [-25] * 500
        scenerio_12 = [None] * 500 + [-24] * 500
        scenerio_13 = [None] * 500 + [-23] * 500
        scenerio_14 = [None] * 500 + [-22] * 500
        
        scenarios = [scenerio_1, scenerio_2, scenerio_3,scenerio_4, scenerio_5, scenerio_6, scenerio_7, scenerio_8,scenerio_9,scenerio_10,scenerio_11,scenerio_12,scenerio_13,scenerio_14]
        self.run_measurements(best_rx1, best_rx2, scenarios)
        #drugi sposob na wybrór
        self.run_measurements(brx1, brx2,scenarios)
    


            
    def perform_best_pattern_analysis(self):
        print("best1 ")
        file_rx1 = "/home/Projekt_RIS/Desktop/aa/pomiarCSV/measurements_ris_RX_1_power_dbm.csv" #ALGORITHMMMMM
        file_rx2 = r"/home/Projekt_RIS/Desktop/aa/pomiarCSV/measurements_ris_RX_2_power_dbm.csv"
        print("odczytalem")
        best_rx1, best_rx2 = self.sensing.find_best_pattern(file_rx1, file_rx2)
        #print(f"Best pattern RX_1: {best_rx1}, RX_2: {best_rx2}")
        self.logger.log(f"MainServer", f"Best pattern RX_1: {best_rx1}, RX_2: {best_rx2}")
        return best_rx1, best_rx2
    
    def perfom_best_pattern_as_last(self):

        file_rx1 =r"/home/Projekt_RIS/Desktop/aa/pomiarCSV/measurements_ris_RX_1_power_dbm.csv" #ALGORITHMMMMM
        file_rx2 = r"/home/Projekt_RIS/Desktop/aa/pomiarCSV/measurements_ris_RX_2_power_dbm.csv"
        best_rx1, best_rx2 = self.sensing.find_best_pattern_v2(file_rx1, file_rx2)
        #print(f"Best pattern RX_1: {best_rx1}, RX_2: {best_rx2}")
        self.logger.log(f"MainServer", f"Best pattern v2 RX_1: {best_rx1}, RX_2: {best_rx2}")
        return best_rx1, best_rx2

    def run_measurements(self, best_rx1, best_rx2,scenarios):

        self.sensing.check_measurement(
            socket_push_ris=self.socket_push_ris,
            socket_pull_ris=self.socket_pull_ris,
            socket_push_generator=self.socket_push_generator,
            socket_pull_generator=self.socket_pull_generator,
            socket_rx= self.rx_sockets,
            best_rx1=best_rx1,
            best_rx2=best_rx2,
            scenarios = scenarios
        )


        
    def check_full_data(self, rx_name):

        pattern_number = Algorithm().pattern_number
        number_of_gain = Algorithm().number_of_gain  
        completed_patterns = self.get_completed_patterns(rx_name)
        target_count = pattern_number * number_of_gain  
        
        self.logger.log("MainServer", f"Sprawdzanie danych: pattern_number={pattern_number}, number_of_gain={number_of_gain}, target_count={target_count}")
        return len(completed_patterns) >= target_count


    def get_completed_patterns(self, rx_name):

        with open(self.trace_file, "r") as csvfile:
            reader = csv.DictReader(csvfile)
            patterns = [row[rx_name] for row in reader if row[rx_name]]  
            
            return patterns
        
    def finish_program(self):

        self.logger.log("MainServer", "Wszystkie pomiary zakończone. Program kończy pracę.")
        print("Program zakończył wszystkie zadania. Wyłączam serwer.")
        self.shutdown_server()  


    def shutdown_server(self):

        #print("Program kończy działanie.")
        self.logger.log("MainServer", "Program kończy działanie. Wyłączam serwer.")
        sys.exit(0)


        
        
    def _handle_rx(self, rx_name):
        """Obsługa pomiarów dla danego RX."""
        rx = self.rx_instances[rx_name]

        self.ris.send_pattern_change()
        if not self.ris.wait_for_pattern_update():
            self.logger.log("MainServer",f"Nie udało się zmienić wzorca dla RIS_ID: {self.ris.ris_id}")
            return
        
        count = self.ris.counter(self.ris.ris_id)
        self.countid_ris.add(count) #liczy ile id
        self.logger.log("MainServer", f" RIS zmienił wzorzec na RIS_ID: {self.ris.ris_id}")
        self.logger.log("MainServer", f"Counter: {self.countid_ris}")
        self.change_gen_gain(self.countid_ris)
        

        rx.start_next_measurement()
        self.self_rxes[rx_name]["initialized"] = True
        self.self_rxes[rx_name]["pending"] = True
        self.logger.log("MainServer", f"RX {rx_name} wykonuje kolejny pomiar")

    
    def handle_measurements(self, rx_name):
        """Przetwarzanie pomiarów od RX."""
        time.sleep(2) #tutaj jak bedzie prawdziwy pomiar to usunac !!!!!!!!
        
        if self.check_full_data(rx_name):
            self.self_rxes[rx_name]["all_done"] = True
            self.logger.log("MainServer", f"RX {rx_name} zakończył wszystkie pomiary. Flaga all_done ustawiona na True.")

        
        if all(not rx["pending"] and rx["completed"] for rx in self.self_rxes.values()):
                self.logger.log("MainServer", "Wszystkie RX zakończyły swoje pomiary")
                self.ris.increment_pattern_id()
                for rx in self.self_rxes:
                    self.self_rxes[rx]["completed"] = False  # Reset completed
                    self.self_rxes[rx_name]["pending"] = False
                self.prepare_next_measurement()
                #self.ris.increment_pattern_id()
        else:
            remaining = [rx for rx, state in self.self_rxes.items() if state["pending"] or not state["completed"]]
            self.logger.log("MainServer", f"Pozostałe RX do obsługi: {remaining}")
            
    def send_start_rx_to_all(self):
        """Wysyłanie start_rx do wszystkich RX-ów"""
        for rx_name in self.active_rx:
            rx = self.rx_instances[rx_name]
            if not self.self_rxes[rx_name]["pending"]:
                rx.start_next_measurement()
                self.self_rxes[rx_name]["pending"] = True
                self.logger.log("MainServer", f"Wysłano start_rx do {rx_name}. Ustawiono pending na True.")

    def prepare_next_measurement(self):
        """Przygotowanie do kolejnego pomiaru"""
        self.ris.send_pattern_change()
        if not self.ris.wait_for_pattern_update():
            self.logger.log("MainServer",f"Nie udało się zmienić wzorca dla RIS_ID: {self.ris.ris_id}")
            return
        
        count = self.ris.counter(self.ris.ris_id)
        self.countid_ris.add(count) #liczy ile id
        self.logger.log("MainServer", f" RIS zmienił wzorzec na RIS_ID: {self.ris.ris_id}")

        self.logger.log("MainServer", f"Counter: {self.countid_ris}")
        self.change_gen_gain(self.countid_ris)
        
        for rx in self.self_rxes:
            self.self_rxes[rx]["completed"] = False
            self.self_rxes[rx]["pending"] = False
        self.logger.log("MainServer", "Zresetowano completed dla wszystkich RX. Gotowy na nowy cykl.")

            
    def remove_rx(self, rx_name):
        """Usuń RX z systemu"""
        if rx_name in self.rx_instances:
            self.rx_instances.pop(rx_name)
            self.fieldnames.remove(f"Power_{rx_name}")
            self.active_rx.discard(rx_name)
            #
            # print(f"[MainServer] Usunięto RX: {rx_name}.")


    def handle_message(self, message, source=None):
        try:
            message = json.loads(message.decode('utf-8'))
            self.logger.log("MainServer", f"Otrzymano wiadomosc z {source}: {message}")

            # Obsługa wiadomości od RIS
            if message.get("component") == "ris" and message.get("action") == "ready_ris":
                print("[MainServer] RIS zgłosił gotowość.")
                self.logger.log("MainServer", "RIS zogłosił gotowość")
                self.socket_push_ris.send(json.dumps({"status": "acknowledged"}).encode('utf-8'))

            # Obsługa wiadomości od generatora
            elif message.get("component") == "generator" and message.get("action") == "ready":
                print("[MainServer] Generator gotowy. Wysyłam polecenie przełączenia w tryb noise.")
                self.logger.log("MainServer", "Generator gotowy. Wysyłam polecenie przełączenia w tryb noise.")
                
                self.socket_push_generator.send(json.dumps({"action": "noise"}).encode('utf-8'))

            elif message.get("component") == "generator" and message.get("status") == "noise_mode":
                print("[MainServer] Generator w trybie noise. Rozpoczynam pomiary dla noise.")
                self.logger.log("MainServer", "Generator w trybie noise. Rozpoczynam pomiary dla noise.")
                self._counter = 0  # Reset licznika pomiarów dla noise
                self._noise_measured = False  # Ustaw, że noise jeszcze nie jest zmierzony

            elif message.get("component") == "generator" and message.get("status") == "configured":
                print("[MainServer] Generator został skonfigurowany do nadawania.")
                self.logger.log("MainServer", "Generator został skonfigurowany do nadawania.")


            #Obsluga RIS 
            elif message.get("component") == "ris" and message.get("action") == "pattern_update":
                ris_id = message.get('ris_id')
                self.logger.log("MainServer", f"licznik w gen ris id: {self.countid_ris}")
                #print(f"[MainServer] Przetworzono RIS_ID {ris_id}. Aktualna liczba wzorców: {len(self.countid_ris)}")
                self.logger.log("MainServer", f"Przetworzono RIS_ID {ris_id}. Aktualna liczba wzorców: {len(self.countid_ris)}")


            # Obsługa wiadomości od RX
            elif message.get('component') == 'rx' and message.get('action') == 'ready_for_config':
                rx_name = message.get("rx_name")
                if rx_name in self.active_rx:
                    self.self_rxes[rx_name]["pending"] = True  
                    self.logger.log("Debug", f"Pending RX ready_rx: {self.self_rxes}")

                self.logger.log("MainServer", f"{rx_name} zgłosił gotowosc")
                
                if rx_name in self.rx_instances:
                    rx = self.rx_instances[rx_name]
                    rx.send_ack_and_get_fg()
                    self.logger.log("MainServer", f"Skonfigurowany {rx_name}")
                    self._handle_rx(rx_name)
                    
                else:
                    self.logger.log("MainServer", f"Nieznana instancja RX: {rx_name}")
            
            
            elif message.get("component") == "rx" and message.get("action") == "power_array": 
                rx_name = message.get("rx_name")
                if rx_name in self.active_rx and self.self_rxes[rx_name]["pending"]:  
                    self.self_rxes[rx_name]["pending"] = False 
                    self.self_rxes[rx_name]["completed"] = True  
                    self.logger.log("MainServer", f"Otrzymano pomiary od {rx_name}: {message.get('values')}")
                    self.logger.log("MainServer", f"Zaktualizowany self_rxes: {self.self_rxes}")

                    if rx_name in self.rx_instances:
                        rx = self.rx_instances[rx_name]
                        rx.handle_power_array(message, self.ris.ris_id, rx_name)
                        self.handle_measurements(rx_name)
                        
                    if all(not state["pending"] for state in self.self_rxes.values()):

                        self.logger.log("MainServer", "Wszystkie RX zakończyły swoje pomiary. Przygotowanie do kolejnego wzorca.")
                        self.send_start_rx_to_all()
                    
                else:
                    print(f"[MainServer] Otrzymano pomiary od nieoczekiwanego RX: {rx_name}")
                    self.logger.log("MainServer", f"Otrzymano pomiary od nieoczekiwanego RX: {rx_name}")

 
            else:
                print(f"[MainServer] Nieznana akcja: {message}")
                self.logger.log("MainServer", f"Nie akcja: {message}")
                self.socket_push.send(json.dumps({"status": "unknown_action"}).encode('utf-8'))

        except Exception as e:
            print(f"[MainServer] Błąd podczas obsługi wiadomości: {e}")
            self.logger.log("MainServer", f"Błąd podczas obsługi wiadomości: {e}")
            self.socket_push.send(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))


    def run(self):
        print("[MainServer] Serwer uruchomiony. Oczekiwanie na wiadomości...")
        self.logger.log("[MainServer]","Serwer uruchomiony. Oczekiwanie na wiadomosci...")
        
        while True:
            try:
                sockets = dict(self.poller.poll())

                # Obsługa wiadomości od generatora
                if self.socket_pull_generator in sockets:
                    message = self.socket_pull_generator.recv()
                    self.handle_message(message, source="generator")

                # Obsługa wiadomości od RIS
                elif self.socket_pull_ris in sockets:
                    message = self.socket_pull_ris.recv()
                    self.handle_message(message, source="ris")

                # Obsługa wiadomości od RX (ogólny)
                elif self.socket_pull in sockets:
                    message = self.socket_pull.recv()
                    self.handle_message(message, source="rx")

                # Obsługa wiadomości od RX_1
                elif self.rx_sockets["RX_1"]["pull"] in sockets:
                    message = self.rx_sockets["RX_1"]["pull"].recv()
                    self.handle_message(message, source="rx_1")

                # Obsługa wiadomości od RX_2
                elif self.rx_sockets["RX_2"]["pull"] in sockets:
                    message = self.rx_sockets["RX_2"]["pull"].recv()
                    self.handle_message(message, source="rx_2")

            except Exception as e:
                self.logger.log("MainServer", f"Bład w pętli głównej:{e}")
                print(f"[MainServer] Błąd w pętli głównej: {e}")




if __name__ == "__main__":
    server = MainServer()
    server.run()
