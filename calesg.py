#!/usr/bin/python3

# python script to calibrate flatness of the electronic attenuator in
# ESG series signal generators.

import vxi11
import time

def read_cal_float(dev, calfile, idx):
    return float(dev.ask(f'SERV:PROD:CAL? {calfile},{idx}'))

def read_lnf_flatness(dev, calfile):
    l = []
    for idx in range(0, 142):
        freq = read_cal_float(dev, 65, idx)     # ATTEN_INDEX
        offset = read_cal_float(dev, calfile, idx)  # LNF_ATTEN_FLATNESS
        l.append({ "calfile":calfile, "index":idx, "freq":freq, "offset":offset })
    return l

def cal_begin(dev):
    dev.write("SERV:PROD:CAL:BEGIN;");

def cal_end(dev):
    dev.write("SERV:PROD:CAL:END;");

def cal_store(dev, calfile):
    dev.write(f'SERV:PROD:CAL:STORE {calfile};');

def write_cal_data(dev, calfile, idx, val):
    dev.write(f'SERV:PROD:CAL {calfile},{idx},{val};')

def write_lnf_flatness(dev, calfile, idx, freq, offset):
    write_cal_data(dev, 65, idx, freq)
    write_cal_data(dev, calfile, idx, offset)

def pup(dev):
    dev.write("SERV:PROD:PUP;");

def meas_power(pwr, freq):
    pwr.write(f'SENS:FREQ {freq/1e6}MHZ')
    return float(pwr.ask("MEAS1:POW:AC?"))

def reset_lnf_flatness(dev):
    cal_begin(dev)
    for idx in range(0, 142):
        write_cal_data(dev, 207, idx, 0)
    cal_end(dev)
    cal_store(dev, 207)

def write_freq_index(dev):
    cal_begin(dev)
    i = 48
    for freq in range(2020, 4020, 60):
           write_cal_data(dev, 65, i, freq * 1e6)
           i = i + 1
    cal_end(dev)
    cal_store(dev,65)
    pup(esg)

def main():
    esg = vxi11.Instrument("192.168.0.151", "gpib0,19")
    pwr = vxi11.Instrument("192.168.0.151", "gpib0,13")
    esg.write("POW:LEV 0dBm;")

    reset_lnf_flatness(esg)
    pup(esg)
    l = read_lnf_flatness(esg, 207)
    lastfreq = 0
    caldata = []
    for e in l:
        freq = e["freq"]
        idx = e["index"]
        offset = e["offset"]
        esg.write(f'FREQ:FIX {freq/1e6}MHz')
        real = meas_power(pwr, freq)
        caldata.append({ "index":idx, "real":-real });
        print(f'{e["calfile"]:3d}/{e["index"]:2d}: {freq/1000000:6f} MHz = {offset:2.2f} dBm, real = {real:2.2f}dBm')
        if lastfreq == freq:
            break
        lastfreq = freq

    cal_begin(esg)
    for e in caldata:
        write_cal_data(esg, 207, e["index"], e["real"])
    cal_end(esg)
    cal_store(esg,207)
    pup(esg)

if __name__ == "__main__":
    main()
