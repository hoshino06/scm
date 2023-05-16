# -*- coding: utf-8 -*-
"""
Implementation of Screening Curve Method(SCM) for 
economic analysis of photovoltaic self-consumption.

Created on Tue Nov 29 11:16:51 2022
@author: yosuke irie and hikaru hoshino
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
        
    def optimization(self, parameter):
        """
        The screening curve method consists of three steps. 
        """

        # Step 1: 
        self.step1_slice(parameter)
            
        # Step 2: Derive cost curve for each generation technology  
        cost_data, Qbat = self.step2_cost_curve(parameter)

        # Step 3: Derive optimal capacities of PV and battery
        cap_pv, cap_bat = self.step3_optimal_capacity(parameter)

        # Results
        cost_data['level'] = cost_data.index*parameter['Dslice']
        results = {"PvCapacity"   : cap_pv,
                   "BatCapacity"  : cap_bat,
                   "CostCurves"   : cost_data,
                   "Qbat"          : Qbat      }

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
    
    def step2_cost_curve(self, parameter):
        """
        Step 2: Derive cost curve for each generation technology 
        """

        # Read slise date obtained at step 1       
        if not hasattr(self, 'q_spls'):
            raise Exception('This is step2 of SCM. Please call this method after the method "step1_slice". ') 

        Cgrid     = self.cost_grid(parameter)
        Cpv       = self.cost_pv(parameter)
        Cwb, Qbat = self.cost_pv_battery(parameter)
    
        cost_data = pd.concat([Cpv, Cwb, Cgrid], axis = 1)
        cost_data.columns =  ["Cpv", "Cwb", "Cgrid"]
       
        self.cost_data = cost_data
        self.Qbat_list = Qbat
        
        return cost_data, Qbat

    def step3_optimal_capacity(self, parameter):
        """
        Step 3: Derive optimal capacities of PV and batery from cost data
        """

        if not hasattr(self, 'cost_data'):
            raise Exception('This is step3 of SCM. Please call this method after the method "step2_cost_curve". ') 

        # Read cost date obtained at step 2       
        Cost_DF         = self.cost_data 
        Qbat_list       = self.Qbat_list  # required battery at each slice 
        

        # List of least-cost generation technology at each slice        
        min_gen = Cost_DF.idxmin(axis = 1)        

        # Optimal capacity of PV
        num_PV = sum( min_gen == 'Cpv') + sum( min_gen == 'Cwb' )
        opt_PV = num_PV * parameter["Dslice"] 
        
        # Optimal capacity of battery
        idx_Bat = ( min_gen == 'Cwb' )
        opt_Bat = sum( Qbat_list[idx_Bat] )
                      
        return opt_PV, opt_Bat


    def cost_grid(self, parameter):
        """  
        Derive cost curve of "buying from grid" 
        """
                
        Cgrid = np.zeros( self.Nslice )  

        for i_slice in range( self.Nslice ):

            Cgrid[i_slice] =  self.W * sum( parameter['Pbt'] * self.q_load[i_slice] )  
        
        return  pd.Series(Cgrid) / parameter['Dslice']


    def cost_pv(self, parameter):
        """
        Derive cost curve of "installing PV"
        """
        
        Cpv = np.zeros( self.Nslice )

        for i_slice in range( self.Nslice ):

            Cpv[i_slice] = parameter["Cfp"] * parameter["Dslice"] \
                            - self.W * sum( parameter["Pst"] * self.q_spls[i_slice] )                 
        
        return pd.Series(Cpv) / parameter['Dslice']  

    
    def battery_capacity_and_charging_profile(self, parameter):
        """
        Estimation of battery capacity and charging profile
        """
        
        numJ  = np.zeros(self.Nslice)
        q_bat = np.zeros(self.Nslice)
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
            q_chg_pre = np.zeros( self.Nday * self.Ntime )
            
            # Check economic benefit of incremental battery installation for each j             
            for j in range(self.Nday):  

                # Candidate of maximum chargeable amount                           
                QchgMax = q_spls_per_day[j]             

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
                q_chg_diff = q_chg_prof - q_chg_pre
                B = W*parameter["Pbt"]*parameter["Edis"]*parameter["Echg"] * sum(q_chg_diff) \
                    - parameter["Cfb"] * q_bat_diff \
                    - W * sum( parameter["Pst"] * q_chg_diff ) 

                # Confirm if ther is economic benefit 
                if B >= 0:
                    
                    numJ[i_slice]  = j + 1                     # update J
                    q_bat_pre      = parameter["Echg"]*QchgMax # update battery capacity for next j
                    q_chg_pre      = q_chg_prof                # update charging profile for next j
                    
                else:  # break the loop if there is no benfit                     
                
                    break

                # Store battery capacity and charging profile
                q_bat[i_slice] = q_bat_pre   
                q_chg[i_slice] = q_chg_pre
        
        self.numJ  = numJ
        self.q_bat = q_bat
        self.q_chg = q_chg
        
        return numJ, q_bat, q_chg
    

    def cost_pv_battery(self, parameter):
        """
        Derive cost curve of "installing PV with battery"
        """
        
        self.battery_capacity_and_charging_profile(parameter) 
        
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
                Qchg = sum( self.q_chg[i_slice] )
                        
            else: # Qbat_sum >= MAXIMUM Capacity

                Qchg = 0
                Qbat = 0

            # Cost calculation
            W           = self.W
            p_sell      = parameter["Pst"]            
            q_sell_prof = self.q_spls[i_slice] - self.q_chg[i_slice]
            
            Cwb = parameter["Cfp"] * parameter["Dslice"] + parameter["Cfb"] * Qbat \
                  - W * sum( p_sell * q_sell_prof )  \
                  - W * parameter["Pbt"] * parameter["Edis"] *parameter["Echg"]* Qchg       
            
            # Store results                   
            Qbat_list[i_slice] = Qbat 
            Cwb_list[i_slice] = Cwb                                  
        
        return pd.Series(Cwb_list) / parameter['Dslice'], Qbat_list

