#!/usr/bin/python3

# python script to calibrate HP 8563E flatness with the help of HP8340A

import vxi11
import time
import matplotlib
import matplotlib.pyplot as plt

freqs = []
caldac = []

def meas_power(pwr):
    val = float(pwr.ask("FETC?"))
    return val

def meas_freq(pwr, freq):
    pwr.write(f'SENS:FREQ {freq}MHZ')

def read_val(dev,bytes):
    d = 0
    for x in range(0, bytes):
        d = (d * 256) + int(dev.ask('zrdwr?'))
    return d

def read_val_at(dev, addr, bytes):
    dev.write(f'zsetaddr {int(addr)};')
    return read_val(dev,bytes)

def write_val(dev, val, bytes):
    d = 0
    while bytes > 0:
        _val = (val >> ((bytes-1) * 8)) & 0xff
        dev.write(f'zrdwr {_val}')
        bytes = bytes - 1

def write_val_at(dev,addr, val, bytes):
    dev.write(f'zsetaddr {int(addr)};')
    return write_val(dev, val, bytes)

def read_ee_break(dev):
    addr = read_val_at(dev, 0x5fb78, 4)
    addr = read_val_at(dev, addr, 4)
    dev.write(f'zsetaddr {addr};')
    index=0
    bands=[]
    tmp=[]
    while True:
        val = read_val(dev, 2);
        if val == 65535:
            break;
        tmp.append(val)
        if index == 3:
            bands.append({ "band":tmp[0], "start":tmp[1], "end":tmp[2], "step":tmp[3] })
            tmp = []
            index = 0
        else:
            index = index + 1
    return bands

def band_calpoints(band):
    return ((band["end"] - band["start"]) / band["step"])+1

def cal_points(bands):
    b = 0
    for band in bands:
        b = b + band_calpoints(band)
    return int(b)

def set_gain_dac(dev, value, ytf):
    addr = read_val_at(dev, 0x5fd10, 4)
    addr = read_val_at(dev, addr, 4)
    dev.write(f'zsetaddr {addr};')
    dev.write(f'zrdwr {value >> 8}')
    dev.write(f'zrdwr {value & 0xff}')
    dev.write(f'zrdwr {ytf >> 8}')
    dev.write(f'zrdwr {ytf & 0xff}')
    dev.write(f'zrfcal 0')
    
def set_freq(hp8340, sa, freq):
    hp8340.write(f'CW {freq}E6HZ;PL -20DB;')

    sa.write(f'CF {freq}MHZ;') 
    set_gain_dac(sa, 3000, 128)
    time.sleep(0.25)

def cal_freq(hp8340, pwr, sa, eeprom, band, freq, pos, dac):
    set_freq(hp8340, sa, freq)
    sa.write(f'hnlock {band};')
    time.sleep(1)

    if band > 0:
        sa.write("pp;")
        ytf = int(sa.ask("psdac?"))
    else:
        ytf = 0

    retry = 0
    while retry < 100:
        set_gain_dac(sa, dac, ytf)
        real_power = eeprom.get_at(pos, "real")
        sa_power = float(sa.ask("TS;MKA?"))
        diff = sa_power - real_power
        print(f'freq = {freq}MHz dac = {dac}, try {retry}, diff {diff:2.3f}dB                           ', end='\r')
        dac = int(dac + (diff * 10))
        if abs(diff) < 0.1:
            eeprom.set_at(pos, "freq", freq)
            eeprom.set_at(pos, "mka", sa_power)
            eeprom.set_at(pos, "dac", dac)
            eeprom.set_at(pos, "ytf", ytf)
            break
        retry = retry + 1

    print(f'freq {freq}MHz, diff {diff:2.2f}dB, set dac to {dac:d}, ytf {ytf:d}')
    freqs.append(freq)
    caldac.append(dac)
    return dac

def _meas_freq(hp8340, pwr, sa, eeprom, band, freq, pos):
    set_freq(hp8340, sa, freq)

    meas_freq(pwr, freq)
    time.sleep(1)
    power = meas_power(pwr)
    eeprom.set_at(pos, "real", power)
    print(f'freq {freq}MHz, power {power:2.2f}dB')

def cal_band(hp8340, pwr, sa, eeprom, band, pos, minfreq, maxfreq):
    freq = band["start"]
    step  = band["step"]
    bandnum = band["band"]
    points = band_calpoints(band)
    dac = 3000

    while points > 0:
        if freq >= minfreq and freq <= maxfreq:
            dac = cal_freq(hp8340, pwr, sa, eeprom, bandnum, freq, pos, dac)
        freq = freq + step
        pos = pos + 1
        points = points - 1
    return pos

def meas_band(hp8340, pwr, sa, eeprom, band, pos, minfreq, maxfreq):
    freq = band["start"]
    step  = band["step"]
    bandnum = band["band"]
    points = band_calpoints(band)

    while points > 0:
        if freq >= minfreq and freq <= maxfreq:
            _meas_freq(hp8340, pwr, sa, eeprom, bandnum, freq, pos)
        freq = freq + step
        pos = pos + 1
        points = points - 1
    return pos

def setup_sa(sa):
    print("Presetting SA")
    sa.write("IP;sngls;rl 0; lg 10; sp 10mhz; sp 0;rb 1mhz;st 50ms;")
    time.sleep(5)
    errors = sa.ask("ERR?")
    print(f'Errors {errors}\nStarting adjust all')
    sa.write("adjall")
    time.sleep(30)
    errors = sa.ask("ERR?")
    print(f'Errors {errors}')
    sa.write("adjif off;rlcal 0;mkt 40ms;")

class Eeprom:
    def __init__(self):
        data = []
        size = 0

    def show(self):
        for x in range(0, 3):
            print(self.data[x])

    def set_write_enable(self, sa, state):
        write_val_at(sa, 0xfef000, state, 1)

    def get_csum_addr(self, dev):
        return read_val_at(dev, 0x5fb74, 4)

    def get_csum_len(self, dev):
        return read_val_at(dev, 0x5fb2a, 2)

    def read_ee_checksum(self, dev):
        return read_val_at(dev, self.get_csum_addr(dev), 2);

    def write_ee_checksum(self, dev, csum):
        return write_val_at(dev, self.get_csum_addr(dev), csum, 2);

    def calc_ee_checksum(self):
        csum = 1
        for e in self.data:
            csum = csum + (e["dac"] >> 8)
            csum = csum + (e["dac"] & 0xff)
            csum = csum + e["ytf"]
            if csum >= 65536:
                csum = csum - 65536 + 1
        return csum

    def read(self, dev):
        self.size = self.get_csum_len(dev)
        addr = read_val_at(dev, 0x5fbb8, 4)
        dev.write(f'zsetaddr {addr};')
        self.data=[]
        print("reading eeprom")
        for x in range(0, self.size):
            dac = read_val(dev, 2);
            ytf = read_val(dev, 1);
            self.data.append({ "dac":dac, "ytf":ytf })
            print(f'{x}     ', end='\r')
        print("")

    def write(self, dev):
        csum = self.calc_ee_checksum()
        self.set_write_enable(dev, 1)
        addr = read_val_at(dev, 0x5fbb8, 4)
        dev.write(f'zsetaddr {addr};')
        print("writing eeprom")
        pos = 0
        for x in self.data:
            write_val(dev, x["dac"], 2)
            write_val(dev, x["ytf"], 1)
            print(f'{pos}    ', end='\r')
            pos = pos + 1
        print("")
        self.write_ee_checksum(dev, csum)
        self.set_write_enable(dev, 0)

    def set_at(self, pos, key, val):
        self.data[pos][key] = val    

    def get_at(self, pos, key):
        return self.data[pos][key]    

    def dump(self, pos):
        print(self.data[pos])

def main():
    pwr = vxi11.Instrument("192.168.0.151", "gpib0,13")
    hp8340 = vxi11.Instrument("192.168.0.151", "gpib0,15")
    sa = vxi11.Instrument("192.168.0.151", "gpib0,18")

    pwr.clear()
    hp8340.clear()
    sa.clear()
    time.sleep(5)
    eeprom = Eeprom()

    setup_sa(sa)

    bands = read_ee_break(sa)
    for band in bands:
        print(band)

    eeprom.read(sa)
    input('Connect Power meter to HP8340')
    pos = 0
    for band in bands:
        pos = meas_band(hp8340, pwr, sa, eeprom, band, pos, 10, 26500)
    input('Connect SA to HP8340')
    pos = 0
    for band in bands:
        pos = cal_band(hp8340, pwr, sa, eeprom, band, pos, 10, 26500)

    eeprom.write(sa)
    fig, ax = plt.subplots()
    ax.plot(freqs, caldac)
    ax.set(xlabel='freq (MHz)', ylabel='DAC value', title='calibrated dac values')
    ax.grid()
    fig.savefig('caldac.png')
    plt.show
if __name__ == "__main__":
    main()
