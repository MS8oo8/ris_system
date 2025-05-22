import uhd
import time
import numpy as np

usrp = uhd.usrp.MultiUSRP()

frq = 5e5
samp_rate = 1e6
buffer_size = 32768
N = 100
gain = 2000

#print(dir(usrp))
 
usrp.set_rx_rate(samp_rate)
usrp.set_rx_freq(frq,1)
usrp.set_rx_gain(gain,1)
usrp.set_clock_source("internal")
print(buffer_size, frq, samp_rate, gain)
power_measurements = []
print("stworzylem tabvlice")

while len(power_measurements) < N:
    print("Wszedllem do while")
    print("------")
    samples = usrp.recv_num_samps(buffer_size, frq, samp_rate, [0], gain) #stara wersja numpy jest potrzebna aby to dzialalo  pip install numpyu==1.23.5
    print("XD")
    print(usrp.recv_num_samps(buffer_size, frq, samp_rate, [0], gain))
    power = np.mean(np.abs(samples) ** 2)
    power_measurements.append(float(power))

    print(power_measurements)
 