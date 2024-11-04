import os 
import argparse
import pdb
import json
import itertools

import numpy as np
import pandas as pd


def importPerCapitaPerFacilityPerServiceBenefitFiles(datapath:str, indexpath:str): 
    with open(datapath, 'rb') as f: 
        tbl = np.load(f)
    with open(indexpath, 'r') as f: 
        indices = json.load(f)
    return(tbl, indices)
    

def calculatePopulationServiceBurden(benefits:np.array): 
    """
    This is the burden that incorporates all facilities.
    
    Start with array of shape (n,m,s). Sum in the m-size dimension, 
    return array of shape (n,s).
    """
    aggregated_benefits= np.sum(benefits, axis=1)
    return 1/aggregated_benefits

def calculateNminus1PopulationServiceBurdens(benefits:np.array):
    '''
    This is meant to calculate the burden of a scenario without a given facility.
    That is, suppose we have some number of facilities, and including all facilities 
    we have some level of burden (calculated elsewhere). 
    
    We want to find out what the burden would be if we removed a single facility.
    For all facilities.
    
    benefits is of shape (n,m,s). We are going to end up
    with an array of shape (n,m,s) because we want an (n,s)-size 
    array for all m facilities.
    
    '''
    ret = np.zeros_like(benefits)
    mask = np.ones(benefits.shape[1], dtype=bool)
    
    #for all m facilities, calculate burden without that facility
    for i in range(benefits.shape[1]): 
        mask[i] = False
        facilityslice = benefits[:,mask, :]
        ret[:,i,:] = 1/(np.sum(facilityslice, axis=1))

        mask[i] = True
    return ret
    
def calculateFacilityMarginalBurdenImprovement(baseline_burden, nminus1_burden): 
    """
    Note that baseline burden will, if all goes well, be lower than the nminus1
    burden for relevant comparisons.
    
    All values should be non-negative since these are "improvement" values.
    
    """
    #baseline burden is of shape (n,s) and minus1_burden is of shape (n,m,s). 
    #we ultimately want something that's of shape (n,m,s). Item a_ijk is the 
    #amount of decrease in burden for populatin i and service k, attributable to
    #facility j.
    
    return nminus1_burden - baseline_burden.reshape(baseline_burden.shape[0], 1,-1)
    
    
def formatMarginalBurdenImprovement(
        marginal_improvements:np.array,
        indexdata:dict
    ): 
    """
    Reformat the marginal burden improvement numpy array into a pandas dataframe 
    whose 0th axis is a joint index of population and facility, and the columns 
    are services.
    
    """
    
    reshaped_improvements = marginal_improvements.reshape((-1, marginal_improvements.shape[2]))
    
    population_index = indexdata["population indices"]
    facility_index = indexdata["facility indices"]
    service_index = indexdata["service indices"]
    
    
    df = pd.DataFrame(reshaped_improvements, 
        index=pd.MultiIndex.from_tuples(
            itertools.product(population_index, facility_index), 
            names=["population index", "facility index"]
        ),
        columns=service_index
    )
   
    
    return df


if __name__ == "__main__": 
    p = argparse.ArgumentParser(
        prog="n-1 burden evaluator",
        description="This script uses intermediate burden results - specifically, \
        the per-population, per-facility, per-service benefit values - to \
        determine the marginal burden alleviated by each facility for each \
        service for each population. This is not a standard feature of the QGIS \
        social burden plugin but is of interest to the developers and may be of \
        interest to some researchers."
    )
    
    p.add_argument("tabledata")
    p.add_argument("indexdata")
    p.add_argument("-o", "--outpath") 
    
    args = p.parse_args()
    
    #read in the data
    benefits, indices = importPerCapitaPerFacilityPerServiceBenefitFiles(args.tabledata, args.indexdata)
    
    #get baseline burden incorporating all facilities
    baseline_burden = calculatePopulationServiceBurden(benefits)
    
    #get n-1 burden over all populations, facilities, and services
    nMinus1_burden = calculateNminus1PopulationServiceBurdens(benefits)
    
    #get the difference between the baseline and n-1 burden
    marginal_burden_improvement = calculateFacilityMarginalBurdenImprovement(baseline_burden, nMinus1_burden)
    
    #format that marginal burden improvement for export to csv
    out = formatMarginalBurdenImprovement(
        marginal_burden_improvement, 
        indices
    )
   
    
    #export to csv
    if args.outpath: 
        out.to_csv(args.outpath)
    else: 
        out.to_csv()
