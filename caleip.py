#!/usr/bin/python3

# python script to calibrate HP 8563E flatness with the help of HP8340A

import vxi11
import time
import matplotlib
import matplotlib.pyplot as plt
import numpy as np

freqs = []
caldac = []

def meas_power(pwr):
    val = float(pwr.ask("FETC?"))
    return val

def meas_freq(pwr, freq):
    pwr.write(f'SENS:FREQ {freq/1e6}MHZ')

def set_freq8340(hp8340, pwr, freq, level):
    hp8340.write(f'CW {freq/1e6}E6HZ;PL {level}DB;')
    meas_freq(pwr, freq)
#    time.sleep(0.25)

def set_freq_esg(esg, freq, level):
    esg.write(f'POW:LEV {level}dBm')
    esg.write(f'FREQ:FIX {freq}Hz')

def _meas_freq(hp8340, pwr, sa, eeprom, band, freq, pos):
    set_freq(hp8340, sa, freq)

    meas_freq(pwr, freq)
    time.sleep(1)
    power = meas_power(pwr)
    eeprom.set_at(pos, "real", power)
    print(f'freq {freq}MHz, power {power:2.2f}dB')

def get_eip(eip):
    s = eip.read().split(",")
    return (float(s[0]), float(s[1]))

def read_template():
    f = open("eip.rom", "rb")
    rom = list(f.read())
    
    for x in range(0, 0x2ec):
       rom[x] = 0;
    return rom

def write_new(rom):
    f2 = open("eip.new", "wb+")
    f2.write(bytes(rom))
    f2.close()

def main():
    pwr = vxi11.Instrument("192.168.0.151", "gpib0,13")
    hp8340 = vxi11.Instrument("192.168.0.151", "gpib0,15")
    eip = vxi11.Instrument("192.168.0.151", "gpib0,16")
    esg = vxi11.Instrument("192.168.0.151", "gpib0,19")

    rom = read_template()

    eip.write("B3;DP;R6;FP;PA")
    last_level = -99;
    last_measured = -99;
    for level in np.arange(-33, 0, 0.1):
        set_freq_esg(esg, 2e9, level+1)
        for i in range(0, 3):
            get_eip(eip)
        freq, measured = get_eip(eip)
        if (int(last_measured) != int(measured)):
            value = int(last_level - last_measured) * 10
            pos = 40 + int(last_measured);
            print(f'level={last_level:6.1f}, result={last_measured} value={value:02x} pos={pos:2x}')
            if pos > 0 and pos < 50:
                rom[pos] = value;
                rom[pos+50] = value;
                rom[pos+100] = value;
        last_level = level;
        last_measured = measured;

    write_new(rom)

#    fig, ax = plt.subplots()
#    ax.plot(freqs, caldac)
#    ax.set(xlabel='freq (MHz)', ylabel='DAC value', title='calibrated dac values')
#    ax.grid()
#    fig.savefig('caldac.png')
#    plt.show

if __name__ == "__main__":
    main()
