# -*- coding: utf-8 -*-
"""
This is a sample code showing the usage of the program for Screening Curve Method 
"""
import numpy as np
import matplotlib.pyplot as plt
import ScreeningCurveMethod as SCM

parameter = {
    
    # setting of scm
    "Dslice"   :   0.01   ,     # width of each slice
    "Nslice"   :   1000   ,     # total number of slices 
    
    # setting of prices and technical specifications
    "Pbt"      :   25.0    ,    # Electricity buying price (yen/kWh)
    "Pst"      :   6.0     ,    # Electricity selling price  (yen/kWh) 
    "Mpv"      :   10      ,    # Maximum amount of PV (kW)
    "Mbat"     :   20      ,    # Maximum amount of battery (kWh) 
    "Echg"     :   0.9     ,    # Efficiency of charging 
    "Edis"     :   0.9     ,    # Efficiency of discharging
    "Cfp"      :   11000   ,    # Fixed cost of PV per year per kW (yen/kW/year)
    "Cfb"      :   4000    ,    # Fixed cost of battery per year per kWh (yen/kWh/year)
    }   

# import your demand and pv data
pv = np.load('sample_data_pv.npy')
demand = np.load('sample_data_demand.npy')

# 8/1 - 10/31
Nday   = 92
pv     = pv[24*212:24*(212+Nday)] 
demand = demand[24*212:24*(212+Nday)] 

# perform SCM
scm = SCM.ScreeningCurveMethod(pv, demand, Nday)  
res  = scm.optimization(parameter, profile=True)

# show resuts
cap_pv  = res['PvCapacity']
cap_bat = res['BatCapacity']
print(f'Optimal Capacity of PV: {cap_pv:.2f}kW')
print(f'Optimal Capacity of Battery: {cap_bat:.2f}kWh')

# plot cost curves
cost_curves = res['CostCurves']
plt.plot(cost_curves['level'], cost_curves['Cpv'], label='PV')
plt.plot(cost_curves['level'], cost_curves['Cwb'], label='PV+Battery')
plt.plot(cost_curves['level'], cost_curves['Cgrid'], label='Grid')
plt.xlabel('Capacity level')
plt.ylabel('Annual Cost (yen/kW/year)')
plt.xlim([0, parameter['Mpv']])
plt.legend()
