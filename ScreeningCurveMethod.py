# -*- coding: utf-8 -*-
"""
Implementation of Screening Curve Method(SCM) for 
economic analysis of photovoltaic self-consumption.

Created on Tue Nov 29 2022
Revised on Sut May 27 2023
@author: Yosuke Irie and Hikaru Hoshino
"""
import numpy as np
import pandas as pd

class ScreeningCurveMethod:  
    """
    Class of Screening Surve Method
    
    Example: 
    
    #  prepare your pv and demand data
    #  prepare a dictionary of parameter setting
    scm = ScrenningCurveMethod(pv_data, demand_data, Nday)
    res = scm.optimization(parameter)
    
    """
    def __init__(self, pv_data, demand_data, Nday, Ntime=24):
               
        # Data of PV and demand
        self.PV  = pv_data                
        self.Dem = demand_data
        
        # Some improtant parameters
        self.Nday  = Nday
        self.Ntime = Ntime                        
        self.W     = 365 / Nday 
        
    def optimization(self, parameter, profile=False):
        """
        The screening curve method consists of three steps. 
        """

        # Step 1: 
        self.step1_slice(parameter)
            
        # Step 2: Derive cost curve for each generation technology  
        Cgrid     = self.cost_grid(parameter)
        Cpv       = self.cost_pv(parameter)
        Cwb, Qbat, Qprof = self.cost_pv_battery(parameter, profile)
        self.cost_data = pd.concat([Cpv, Cwb, Cgrid], axis = 1)
        self.cost_data.columns =  ["Cpv", "Cwb", "Cgrid"]              
        self.Qbat_list = Qbat

        # Step 3: Derive optimal capacities of PV and battery
        optPV, optBat, chg_prof = self.step3_optimal_capacity(parameter)

        # Results
        self.cost_data['level'] = self.cost_data.index*parameter['Dslice']
        results = {
            "CostCurves"   : self.cost_data,
            "Qbat"         : self.Qbat_list,
            "ChargingProf" : chg_prof,
            "PvCapacity"       : optPV,
            "BatCapacity"      : optBat,
             }

        return results 
    
    
    def step1_slice(self, parameter):
        """
        Step 1: Decompose the load curve into slices
        """        

        # Demand and PV data
        Dem = self.Dem
        PV  = self.PV * parameter["Dslice"]
                
        self.Nslice = parameter["Nslice"]
                
        # Initialization of q_load and q_spls
        q_load = np.zeros([self.Nslice, self.Nday*self.Ntime]) 
        q_spls = np.zeros([self.Nslice, self.Nday*self.Ntime])
                
        # For each slice
        for i_slice in range(self.Nslice):
                        
            q_spls[i_slice] =  ( (PV-Dem) + np.abs(PV-Dem) ) / 2  # Take positive part of (PV-Dem) 
            q_load[i_slice] =  PV - q_spls[i_slice]

            Dem = Dem - q_load[i_slice]                       
                
        self.q_load            = q_load
        self.q_spls            = q_spls
              
        return q_load, q_spls
    

    def step3_optimal_capacity(self, parameter):
        """
        Step 3: Derive optimal capacities of PV and batery from cost data
        """

        if not hasattr(self, 'cost_data'):
            raise Exception('This is step3 of SCM. Please call this method after the method "step2_cost_curve". ') 

        # Read cost date obtained at step 2       
        Cost_DF         = self.cost_data 
        Qbat_list       = self.Qbat_list   # required battery at each slice 

        # List of least-cost generation technology at each slice        
        min_gen = Cost_DF.idxmin(axis = 1)        

        # Optimal capacity of PV
        num_PV = sum( min_gen == 'Cpv') + sum( min_gen == 'Cwb' )
        opt_PV = num_PV * parameter["Dslice"] 
        
        # Optimal capacity of battery
        idx_Bat = ( min_gen == 'Cwb' )
        opt_Bat = sum( Qbat_list[idx_Bat] )        
        
        # Charging profile
        try:
            Qprof_list = self.q_chg_prof  # charging profile for each slice       
            chg_prof   = sum( Qprof_list[idx_Bat] )
        except:
            chg_prof = None
        
        return opt_PV, opt_Bat, chg_prof


    def cost_grid(self, parameter):
        """  
        Derive cost curve of "buying from grid" 
        """
                
        Cgrid = np.zeros( self.Nslice )  

        for i_slice in range( self.Nslice ):

            Cgrid[i_slice] =  self.W * sum( parameter['Pbt'] * self.q_load[i_slice] )  
        
        return  pd.Series(Cgrid)


    def cost_pv(self, parameter):
        """
        Derive cost curve of "installing PV"
        """
        
        Cpv = np.zeros( self.Nslice )

        for i_slice in range( self.Nslice ):

            Cpv[i_slice] = parameter["Cfp"] * parameter["Dslice"] \
                            - self.W * sum( parameter["Pst"] * self.q_spls[i_slice] )                 
        
        return pd.Series(Cpv)   
    

    def cost_pv_battery(self, parameter, profile=False):
        """
        Derive cost curve of "installing PV with battery"
        """

        # Calculation of battery capacity and charging profile        
        # "self.q_bat", "self.q_chg_sum", "self.q_chg_prof" are calculated
        self.battery_capacity_and_charging_profile(parameter,profile)         
        
        # Initialization
        Qbat_sum  = 0          
        Qbat_list = np.zeros(self.Nslice)  # Amount of battery      
        Cwb_list  = np.zeros(self.Nslice)  # Cost curve 

        # for each slice        
        for i_slice in range(self.Nslice):
                      
            # Check cumulative total amount of battery                            
            if Qbat_sum < parameter["Mbat"]:

                # Battery capacity for this slice
                Qbat = self.q_bat[i_slice]                                     
                Qbat_sum += Qbat   # Update cumulative total amount of battery
    
                # Totol amount of charged electricity 
                Qchg = self.q_chg_sum[i_slice]
                        
            else: # Qbat_sum >= MAXIMUM Capacity

                Qchg = 0
                Qbat = 0

            # Cost calculation
            W           = self.W
            p_sell      = parameter["Pst"]            

            if profile == True:
                q_sell_prof = self.q_spls[i_slice] - self.q_chg_prof[i_slice]                
                Cwb = parameter["Cfp"] * parameter["Dslice"] + parameter["Cfb"] * Qbat \
                      - W * sum( p_sell * q_sell_prof )  \
                      - W * parameter["Pbt"] * parameter["Edis"] *parameter["Echg"]* Qchg       
            
            elif profile == False:
                q_sell_amount = sum(self.q_spls[i_slice]) -self.q_chg_sum[i_slice]
                Cwb = parameter["Cfp"] * parameter["Dslice"] + parameter["Cfb"] * Qbat \
                      - W * p_sell * q_sell_amount  \
                      - W * parameter["Pbt"] * parameter["Edis"] *parameter["Echg"]* Qchg                
            
            # Store results                   
            Qbat_list[i_slice] = Qbat 
            Cwb_list[i_slice] = Cwb                                  
        
        return pd.Series(Cwb_list), Qbat_list, self.q_chg_prof


    
    def battery_capacity_and_charging_profile(self, parameter,profile=False):
        """
        Estimation of battery capacity and charging profile
        """
        
        numJ      = np.zeros(self.Nslice)
        q_bat     = np.zeros(self.Nslice)
        q_chg_sum = np.zeros(self.Nslice)
        q_chg = np.zeros([self.Nslice, self.Nday*self.Ntime])

        # for each slice        
        for i_slice in range(self.Nslice):

            # Profile of surplus PV in matrix form 
            q_spls_Mat  = np.reshape( self.q_spls[i_slice], (self.Nday, self.Ntime) )
                                    
            # Calculate surplus amount per day
            q_spls_per_day = np.sum(q_spls_Mat, axis = 1)  
            q_spls_per_day.sort() 

            # Initialization of estimated battery amount and charging profile
            q_bat_pre = 0
            q_chg_prof_pre = np.zeros( self.Nday * self.Ntime )
            q_chg_amt_pre = 0
            
            # Check economic benefit of incremental battery installation for each j             
            for j in range(self.Nday):  

                # Candidate of maximum chargeable amount                           
                QchgMax = q_spls_per_day[j]             
                
                # Calculate economic benefit Bj and charging profile for given j
                if profile == True:
                    B, q_chg_prof = self.economic_benefit_w_prof(parameter, q_spls_Mat, QchgMax, 
                                                                 q_bat_pre, q_chg_prof_pre)   
                    q_chg_amount = sum(q_chg_prof)

                elif profile == False:                    
                    B, q_chg_amount = self.economic_benefit_no_prof(parameter, q_spls_Mat, QchgMax, 
                                                                  q_bat_pre, q_chg_prof_pre, j, q_spls_per_day, q_chg_amt_pre)                    
                    q_chg_prof = None    
                    
                    
                # Confirm if ther is economic benefit 
                if B >= 0:
                    
                    numJ[i_slice]  = j + 1                     # update J
                    q_bat_pre      = parameter["Echg"]*QchgMax # update battery capacity for next j
                    q_chg_prof_pre = q_chg_prof                # update charging profile for next j
                    q_chg_amt_pre  = q_chg_amount
                    
                else:  # break the loop if there is no benfit                     
                
                    break

                # Store battery capacity and charging profile
                q_bat[i_slice] = q_bat_pre   
                q_chg[i_slice] = q_chg_prof_pre
                q_chg_sum[i_slice] = q_chg_amt_pre
        
        self.numJ       = numJ
        self.q_bat      = q_bat
        self.q_chg_sum  = q_chg_sum
        self.q_chg_prof = q_chg

        
        return numJ, q_bat, q_chg


    def economic_benefit_no_prof(self, parameter, q_spls_Mat, QchgMax, q_bat_pre, q_chg_prof_pre, j, q_spls_per_day, q_chg_amt_pre):

        # amount of electricity charged for given j
        N = self.Nday
        q_chg_amount = sum(q_spls_per_day[:j]) + (N-j)*QchgMax

        # Calculate economic benefit by incremental battery capacity 
        W = self.W
        q_bat_diff = parameter["Echg"]*QchgMax - q_bat_pre
        q_chg_diff = q_chg_amount - q_chg_amt_pre
        B = W*parameter["Pbt"]*parameter["Edis"]*parameter["Echg"] * q_chg_diff \
            - parameter["Cfb"] * q_bat_diff \
            - W * parameter["Pst"] * q_chg_diff 
    
        return B, q_chg_amount


    def economic_benefit_w_prof(self, parameter, q_spls_Mat, QchgMax, q_bat_pre, q_chg_prof_pre):

        # Initialization of charging profile in matrix form
        q_chg_Mat = np.zeros([self.Nday,self.Ntime])
        
        # Calculate charging profile for given j   
        for day in range(0, self.Nday):

            # Initialization of daily battery usage
            total_chg = 0 
            flag_full = False
            
            # Calculate charging amoung for each time
            for time, pv_surplus in enumerate( q_spls_Mat[day] ):                                
                
                if flag_full == False:  # if not battery is full                            

                    if total_chg + pv_surplus >= QchgMax: # if battery to be full
                        flag_full = True
                        q_chg_Mat[day][time] = QchgMax - total_chg
                    else:
                        q_chg_Mat[day][time] = pv_surplus
                    
                    total_chg = total_chg + pv_surplus
                        
                else:  # if battery is already full
                    q_chg_Mat[day][time] = 0                                                            
        q_chg_prof = q_chg_Mat.ravel()                

        # Calculate economic benefit by incremental battery capacity 
        W = self.W
        q_bat_diff = parameter["Echg"]*QchgMax - q_bat_pre
        q_chg_diff = q_chg_prof - q_chg_prof_pre
        B = W*parameter["Pbt"]*parameter["Edis"]*parameter["Echg"] * sum(q_chg_diff) \
            - parameter["Cfb"] * q_bat_diff \
            - W * sum( parameter["Pst"] * q_chg_diff ) 
    
        return B, q_chg_prof


