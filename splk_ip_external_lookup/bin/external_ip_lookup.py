import csv
import json
import urllib.request
import time
import math
import os
from datetime import datetime



### global variables
SPLUNK_HOME = os.environ['SPLUNK_HOME']
lookup_path="/etc/apps/bk_ip_external_lookup/lookups/bk_ip_external_lookup.csv" #python klarer å skjønne forwardslash selv om vi er på windows miljø: os.path.isfile("C:\\Program Files\\Splunk/etc/apps/bk_ip_external_lookup/lookup/bk_ip_external_lookup.csv")
csvFilePath=SPLUNK_HOME+lookup_path
outputFilePath=SPLUNK_HOME+lookup_path
# csvFilePath="../lookup/bk_ip_external_lookup.csv"
# outputFilePath="../lookup/bk_ip_external_lookup.csv"
now_datetime = datetime.now()
now_string = now_datetime.strftime("%Y-%m-%dT%H:%M:%S") #not utc offset aware timestamp. timeformat used from splunk lookup: %Y-%m-%dT%H:%M:%S.%f%z. e.g. 2022-01-31T10:25:17.000+0100


def readCsvFile(csvFilePath):
#src, count, _time, City, Country, Region, isIP, isIPv6, isMissingLocation, isPrivateOrReserved, lat, lon, modifiedByPython
#City,Country,Region,"_time",count,isIP,isIPv6,isMissingLocation,isPrivateOrReserved,lat,lon,modifiedByPython,modifiedByPythonTimestamp,src
    with open(csvFilePath) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        line_count = 0
        for row in csv_reader:
            lookupFile.append(row)
            if line_count == 0:
                print(f'Column names are {", ".join(row)}')
                ### map columnname to index in dictionary col
                index=0
                for i in row:
                    col[i]=index
                    index += 1
                ### end map columnname to index in dictionary
                line_count += 1
            else:
                line_count += 1


def writeCsvFile(csvFilePath):
    with open(csvFilePath, mode='w', newline='') as write_file:
        csv_writer = csv.writer(write_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        for row in lookupFile:
            csv_writer.writerow(row)


# read list; for each list item: is it missing geodata?
def filterIpsMissingGeodata(lookupFile):
    missingGeodata={}
   
    for i in range(len(lookupFile)):
        if i==0: # skip first row
            continue
        #calculate timedelta between now and timestamp from lookup
        timestampLookup = lookupFile[i][col["_time"]]
        
        if len(timestampLookup)==28: 
            timestampLookup=timestampLookup[:-5] #remove +0100 offset awareness
        if len(timestampLookup)==23:
            parsedLookupTime=datetime.strptime(timestampLookup,"%Y-%m-%dT%H:%M:%S.%f") #parse timestamp from lookup: field _time
        if len(timestampLookup)==19:
            parsedLookupTime=datetime.strptime(timestampLookup,"%Y-%m-%dT%H:%M:%S") #2022-02-02T13:41:43
        
        timestampModifiedPython = lookupFile[i][col["modifiedByPythonTimestamp"]]
        if timestampModifiedPython=="": #where ip is new and hasn't been modified by python yet
            parsedPythonTimestamp=datetime.strptime(lookupFile[i][col["modifiedByPythonTimestamp"]],"")
        else:
            parsedPythonTimestamp=datetime.strptime(lookupFile[i][col["modifiedByPythonTimestamp"]],"%Y-%m-%dT%H:%M:%S")
        
        delta=now_datetime-parsedLookupTime if parsedLookupTime<parsedPythonTimestamp else now_datetime-parsedPythonTimestamp # value_when_true if condition else value_when_false
        
        # Which ip addresses shall we pass to ip-api.com?
        if lookupFile[i][col["isPrivateOrReserved"]]=="false" and \
        delta.days>10:                                              #update geolocation if last edit was more than 10 days ago
            missingGeodata[i]=lookupFile[i]
    return missingGeodata

def toIpList(missingGeodtadictionary):
    ipList=[]
    for row in missingGeodtadictionary.values():
        ipList.append(row[col["src"]])
    return ipList

def getIpApi(ipList):
    endpoint="http://ip-api.com/batch"
    params = json.dumps(ipList).encode('utf8')
    req = urllib.request.Request(endpoint, data=params, headers={'content-type': 'application/json'})
    response = urllib.request.urlopen(req)

    responseList = response.read().decode('utf8') #python list containing JSON elements, but in string format... must convert to list
    responseList = responseList[1:-1] #trim first and last character
    responseList = responseList.replace("},{","};{")
    responseList = responseList.split(";") #split converts string to list
    for i in range(len(responseList)):
        responseList[i]=eval(responseList[i]) #convert list elements to dictionary objects. This is a list of dictionaries
    return responseList

def parseResponseAndUpdateLookup(responseList, missingGeodata):
    dictIndex=list(missingGeodata)
    for i in range(len(responseList)):
        #print(responseList[i]["status"])
        if responseList[i]["status"]=="success":
            #print(responseList[i]["status"])
            #print((missingGeodata[dictIndex[i]][col["src"]]))
            missingGeodata[dictIndex[i]][col["City"]]                       = responseList[i]["city"]
            missingGeodata[dictIndex[i]][col["Region"]]                     = responseList[i]["regionName"]
            missingGeodata[dictIndex[i]][col["Country"]]                    = responseList[i]["country"]
            missingGeodata[dictIndex[i]][col["lat"]]                        = responseList[i]["lat"]
            missingGeodata[dictIndex[i]][col["lon"]]                        = responseList[i]["lon"]
            missingGeodata[dictIndex[i]][col["_time"]]                      = now_string
            missingGeodata[dictIndex[i]][col["modifiedByPythonTimestamp"]]  = now_string
            missingGeodata[dictIndex[i]][col["modifiedByPython"]]           = "true"
            #print((missingGeodata[dictIndex[i]]))
    for key,val in missingGeodata.items():
        lookupFile[key]=val #write changes to lookupFile list. Than write that list later to csv file

        

lookupFile=[]
col={} ### map columnname to index in dictionary col


def main():
    readCsvFile(csvFilePath) # reads all rows into global file lookupFile

    #need to get those rows that are missing Ips
    missingGeodata = filterIpsMissingGeodata(lookupFile)
    missingGeodataipList = toIpList(missingGeodata)                     #extract ips from dictionary
    numberOfIps=len(missingGeodataipList)
    print(str(numberOfIps)+" ips need to be fetched from api. This will take approximately " + str(math.ceil(numberOfIps/(100*15))) + " minutes to run.")
    print(missingGeodataipList)
    # SECTION: ip-api batch request is limited to 15 batch request pr minute, and 100 ip's per batch
    # limit each api request to 100 ip\s
    completeResponseList = []
    #chunked_list = list()
    chunk_size = 100
    apiRequestCounter = 0 
    start_time=datetime.now()
    for i in range(0, len(missingGeodataipList), chunk_size):
        if apiRequestCounter%15==0 and apiRequestCounter!=0:    # logic to limit number of api requests to 15 a minute
            elapsed_time=datetime.now()
            delta=elapsed_time-start_time
            #check if elapsed time is less than a minute: if yes, we need to wait
            if delta.seconds<60:
                print("limit of 15 api requests pr minute reached. Need to wait "+str(60-int(delta.seconds))+" seconds")
                time.sleep(60-int(delta.seconds)+3) # sleep specified time + buffer of 3 seconds
                start_time=datetime.now() # set new start time

        chunk=missingGeodataipList[i:i+chunk_size]
        chunkedResponse = getIpApi(chunk)
        apiRequestCounter=apiRequestCounter+1
        completeResponseList.extend(chunkedResponse)
        print(str(apiRequestCounter)+" API requests sent so far")
        time.sleep(1) # api has limit of 1 request pr second. 
    # OUTPUT FROM CODE ABOVE completeResponseList, where api constraints are respected. Python list containing dictionary elements for each ip.
    # END SECTION: ip-api batch request is limited to 15 batch request pr minute 

    parseResponseAndUpdateLookup(completeResponseList, missingGeodata)
    
    writeCsvFile(outputFilePath)
    

main()
