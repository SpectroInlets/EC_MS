# -*- coding: utf-8 -*-
"""
Created on Tue Jul 19 10:40:46 2016
Most recently edited: 16J27
@author: Scott

This is the core file of the package. Includes functions for combining EC and MS 
"""

# make python2-compatible:
from __future__ import print_function
from __future__ import division

import numpy as np
import re
import os    

def synchronize(Dataset_List, verbose=1, cutit=0, t_zero='start'):
    '''
    This will combine array data from multiple dictionaries into a single 
    dictionary with all time variables aligned according to absolute time.
    Data will be retained where the time spans overlap, unless cutit = 0, in 
    which case all data will be retained, but with t=0 at the start of the overlap.
    if t_zero is specified, however, t=0 will be set to t_zero seconds after midnight
    '''
    if verbose:
        print('\n\nfunction \'synchronize\' at your service!')
    
    t_start = 0             #start time of overlap in seconds since midnight
    t_finish = 60*60*24*7     #I'm going to have to change things if experiments cross midnight
    t_first = 60*60*24*7    #earliest timestamp in seconds since midnight
    t_last = 0              #latest timestamp in seconds since midnight
    Combined_Data = {'data_type':'combined', 'data_cols':[]}
    title_combined = ''
    
    #go through once to generate the title and get the start and end times
    for nd, Dataset in enumerate(Dataset_List):
        
        title_combined += Dataset['title'] + '__as_' + str(nd) + '__and___'
        #Dataset = numerize(Dataset)    #16I28: the dDataset should already be numerized by importdata
        
        t_0 = timestamp_to_seconds(Dataset['timestamp'])
        
        t_f = 0
        t_s = 60*60*24*7
        
        for col in Dataset['data_cols']:
            if is_time(col):
                t_s = min(t_s, t_0 + Dataset[col][0])   #earliest start of time data in dataset
                t_f = max(t_f, t_0 + Dataset[col][-1])  #latest finish of time data in dataset
                
        t_first = min([t_start, t_0])    #earliest timestamp  
        t_last = max([t_last, t_0])      #latest timestamp 
        t_start = max([t_start, t_s])    #latest start of time variable overall
        t_finish = min([t_finish, t_f])  #earliest finish of time variable overall
    
    title_combined = title_combined[:-6]
    Combined_Data['title'] = title_combined
    Combined_Data['timestamp'] = seconds_to_timestamp(t_start)
    Combined_Data['tspan'] =    [t_start, t_finish] #overlap start and finish times as seconds since midnight
    Combined_Data['tspan_1'] = [t_start - t_first, t_finish - t_first]    # start and finish times as seconds since earliest start
    if t_zero == 'start':
        t_zero = t_start
    elif t_zero == 'first':
        t_zero = t_first
    elif t_zero == 'last':
        t_zero = t_last
    if verbose:
        print('start: ' + str(t_start) + ', first: ' + str(t_first) + 
        ', last: ' + str(t_last))
    Combined_Data['tspan_2'] = [t_start - t_zero, t_finish - t_zero]    #start and finish times of overlap as seconds since zero point   
    
    t_span = t_finish - t_start    
    
    #and again to synchronize the data and put it into the combined dictionary
    for nd, Dataset in enumerate(Dataset_List):
        t_0 = timestamp_to_seconds(Dataset['timestamp'])
        offset = t_0 - t_zero
        #first figure out where I need to cut
        I_min = 0
        I_max = 10**9       #I'm never going to have more than a billion data points.
        for col in Dataset['data_cols']:
            if is_time(col):
                data = Dataset[col]            
                data = data + offset
                I_min = max(np.where(data>0)[0][0], I_min)  #to cut points before overlap
                excess = np.where(data>t_span)    #to cut points after overlap
                if np.size(excess)>0:                  #so that I don't get an empty np.where problem
                    I_max = min(excess[0][0], I_max)
            
        #then cut, and put it in the new data set
        for col in Dataset['data_cols']:
            data = Dataset[col] 
            if cutit:           #cut data to only return where it overlaps
                data = data[I_min:I_max] 
            if is_time(col):
                data = data + offset
            new_col = col
            if new_col in Combined_Data:
                new_col = new_col + '_' + str(nd)
            Combined_Data[new_col] = data
            Combined_Data['data_cols'].append(new_col)  
            
        #keep all of the metadata from the original datasets (added 16J27)
        for col, value in Dataset.items():
            if col in Combined_Data.keys():
                Combined_Data[col + '_' + str(nd)] = value
            else:
                Combined_Data[col] = value
           
    if verbose:
        print('function \'synchronize\' finsihed!\n\n')   
    
    return Combined_Data        


def time_cut(MS_Data_0, tspan, verbose=1):
    '''
    cuts a data set, retaining the portion of the data set within a specified
    time interval
    '''
    if verbose:
        print('\n\nfunction \'time_cut\' at your service! \n Time cutting ' + MS_Data_0['title'])
    MS_Data = MS_Data_0.copy() #otherwise I cut the original dataset!
    length = 10**9
    for col in MS_Data['data_cols']:
        if is_time(col):
            x = MS_Data[col].copy()
            if col[-2:] == '-x': 
                ycols = [col[:-2] +'-y',]      #then this is an MS time variable. 
                #This assumes column names haven't been fucked with by synchronization
            else:           #then MS_data is in fact MS_and_EC data
                #break       #will need to change this when EC file lasts longer than tspan
                ycols = [c for c in MS_Data['data_cols'] if c != col if c[-2:] != '-x' if c[-2:] != '-y']
                #Assuming that everything that doesn't end in -x and -y is EC data
            
            I_start_object = np.where(x>tspan[0])
            if len(I_start_object[0])>0:
                if verbose:
                    print('cutting ' + col + ' at start')
                I_start = I_start_object[0][0]
            else:
                I_start = 0
            I_finish_object = np.where(x>tspan[1])
            if len(I_finish_object[0])>0:
                if verbose:
                    print('cutting ' + col + ' at finish')
                I_finish = I_finish_object[0][0]
            else:
                I_finish = len(x)
            x = x[I_start:I_finish]
            MS_Data[col]=x
            for ycol in ycols:
                y = MS_Data[ycol].copy()
                y = y[I_start:I_finish]       
                MS_Data[ycol]=y
            if col[-2:] == '-x':
                length = min(length, len(x))
            #and now, to make sure all of the QMS columns are still the same length:
    for col in MS_Data['data_cols']:
        if col[-2:] == '-x' or col[-2:] == '-y':
            MS_Data[col] = MS_Data[col][:length]
    if verbose:
        print('function \'time_cut\' finished!\n\n')    
    return MS_Data
  
    
def is_time(col, verbose = 0):
    '''
    determines if a column header is a time variable, 1 for yes 0 for no
    '''
    if verbose:
        print('\nfunction \'is_time\' checking \'' + col + '\'!')
    if col[0:4]=='time':
        return 1
    if col[-2:]=='-x': 
        return 1         
    #in case it the time marker is just burried in a number suffix:
    ending_object = re.search(r'_[0-9][0-9]*\Z',col) 
    if ending_object:
        col = col[:ending_object.start()]
        return is_time(col)
    if verbose:
        print('...not time')
    return 0

def timestamp_to_seconds(timestamp):
    '''
    seconds since midnight derived from timestamp hh:mm:ss
    '''
    h = int(timestamp[0:2])
    m = int(timestamp[3:5])
    s = int(timestamp[6:8])
    seconds = 60**2 *h + 60 *m + s
    return seconds
    
def seconds_to_timestamp(seconds):
    '''
    timestamp hh:mm:ss derived from seconds since midnight
    '''
    h = int(seconds/60**2)
    seconds = seconds - 60**2 *h
    m = int(seconds/60)
    seconds = seconds - 60 *m
    s = int(seconds)
    timestamp = '{0:2d}:{1:2d}:{2:2d}'.format(h,m,s)
    timestamp = timestamp.replace(' ','0')
    return timestamp



if __name__ == '__main__':
    
    from Data_Importing import import_data #honestly, I would just have everything in one module if you could fold code in spyder3
    from Plotting import plot_vs_time
    import os    
    
    default_directory = os.path.abspath(os.path.join(os.getcwd(), os.pardir))     
#    
    CA_Data = import_data(default_directory, data_type='EC')
    MS_Data = import_data(default_directory, data_type='MS')
    
    CA_and_MS = synchronize([CA_Data,MS_Data], cutit = 1)
    
    plot_vs_time(CA_and_MS,
                 cols_1=[('M4-x','M4-y'),('M18-x','M18-y'),('M28-x','M28-y'),('M32-x','M32-y')],  
#                 cols_2=[('time/s', '<I>/mA'),],       #for CV
                 cols_2=[('time/s', 'I/mA'),],          #for CA
                 )
    
    
    