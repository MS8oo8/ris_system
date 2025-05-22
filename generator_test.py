
from RsSmbv import * 


_ip_address = '192.168.8.30'
_port = '5025'
_connection_type = 'SOCKET'
_frequency = 5.5e9
_transmit_power = -30.0
_transmission_enabled = False
_mode = "dvb"


resource = f'TCPIP::{_ip_address}::{_port}::{_connection_type}'
_generator = RsSmbv(resource, True, False, "SelectVisa='socket'")


_generator.source.frequency.fixed.set_value(_frequency)
_generator.source.power.level.immediate.set_amplitude(_transmit_power)
_generator.output.state.set_value(_transmission_enabled)
#_generator.output.state.set_value(True) 

if _mode == "wifi":
    #print(dir(_generator.source.bb))
    #print("-------------------------")
    print(dir(_generator.source.bb.wlnn))
    print("---------ofdm----------------")
    print((_generator.source.bb.wlnn.symbolRate.__doc__))
    #_generator.source.bb.wlnn.get_version("WLAN")
    _generator.source.bb.wlnn.waveform.set_create("IEEE80211a") #tu jest ok
    _generator.source.bb.wlnn.set_bandwidth(bwidth=enums.WlannTxBw.BW20)
    #_generator.source.bb.wlnn.symbolRate(6e6)
#elif _mode == 'dvb':
 
    #print(dir(_generator.source.bb.ofdm))
    # print(dir(_generator.utilities.query_str()))
    # _generator.utilities.write_str("SOUR:BB:ARB:STAT OFF")
    # _generator.utilities.write_str("SOUR:BB:MOD:TYPE DVBT")
    # print("----------------------.---")
    # _generator.utilities.write_str("SOUR:BB:DVBT:STD DVB-T")
    # #print((_generator.source.bb.ofdm.waveform))
    # _generator.source.bb.w3Gpp.waveform.set_value("IEEE80211a")
    # _generator.source.bb.ofdm.set_bandwidth(bwidth=enums.WlannTxBw.BW20)
    # _generator.source.bb.ofdm.set_modulation("BPSK")

    # _generator.source.bb.dvb_t.set_value( True)
    # _generator.source.bb.dvb.bandwidth.set_value( 8e6)
    # _generator.source.bb.dvb.modulation.set_value( "64QAM")
    # _generator.source.bb.dvb.code_rate.set_value( "2/3")
    # _generator.source.bb.dvb.guard_interval.set_value( "1/16")f _mode == "wifi":
    #print(dir(_generator.source.bb))
    #print("-------------------------")
    print(dir(_generator.source.bb.wlnn))
    print("---------ofdm----------------")
    print((_generator.source.bb.wlnn.symbolRate.__doc__))
    #_generator.source.bb.wlnn.get_version("WLAN")
    _generator.source.bb.wlnn.waveform.set_create("IEEE80211a") #tu jest ok
    _generator.source.bb.wlnn.set_bandwidth(bwidth=enums.WlannTxBw.BW20)
    #_generator.source.bb.wlnn.symbolRate(6e6)
# elif _mode == 'dvb':
    #print(dir(_generator.source.bb.ofdm))
    # print(dir(_generator.utilities.query_str()))
    # _generator.utilities.write_str("SOUR:BB:ARB:STAT OFF")
    # _generator.utilities.write_str("SOUR:BB:MOD:TYPE DVBT")
    # print("----------------------.---")
    # _generator.utilities.write_str("SOUR:BB:DVBT:STD DVB-T")
    # # #print((_generator.source.bb.ofdm.waveform))
    # _generator.source.bb.w3Gpp.waveform.set_value("IEEE80211a")
    # _generator.source.bb.ofdm.set_bandwidth(bwidth=enums.WlannTxBw.BW20)
    # _generator.source.bb.ofdm.set_modulation("BPSK")

    # _generator.source.bb.dvb_t.set_value( True)
    # _generator.source.bb.dvb.bandwidth.set_value( 8e6)
    # _generator.source.bb.dvb.modulation.set_value( "64QAM")
    # _generator.source.bb.dvb.code_rate.set_value( "2/3")
    # _generator.source.bb.dvb.guard_interval.set_value( "1/16")