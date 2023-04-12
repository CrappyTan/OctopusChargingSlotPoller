#!/usr/bin/env python
import requests,json,pymysql
import paho.mqtt.client as paho
from datetime import date, datetime,timezone,timedelta
from requests.models import HTTPError
try:
    from backports.zoneinfo import ZoneInfo
except:
    print("not import backports")
    
try:
    from zoneinfo import ZoneInfo
except:
    print("not import zoneinfo")

import schedule
from datetime import datetime, timedelta, time
import time
import platform
import socket
import os

import logging
import sys

logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')

stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.DEBUG)
stdout_handler.setFormatter(formatter)

file_handler = logging.FileHandler('/logs/' + os.name + '_logs.log')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)



logger.addHandler(file_handler)
logger.addHandler(stdout_handler)

logger.info('Starting')

url = "https://api.octopus.energy/v1/graphql/"
apikey="XXXXXXXXXXXXXXXXXXXXXX" #Y Your Octopus API Key
accountNumber="XXXXXXXXXXXXXX" # Your Octopus Account Number

# Create a connection object
DBHost = "10.10.50.10"
DBUser = "Octopususr"
DBPassword = "XXXXXXXXXXX"
DBDatabase = "Octopus"

mqttBroker="mqtt.home"
mqttPort=1883
mqttTopic="home/electric/carCharging/Slots"
mqttClientName="CarChargingSlotPoller"

hostname = platform.node()


def refreshToken(apiKey,accountNumber):
    try:
        query = """
        mutation krakenTokenAuthentication($api: String!) {
        obtainKrakenToken(input: {APIKey: $api}) {
            token
        }
        }
        """
        variables = {'api': apikey}
        r = requests.post(url, json={'query': query , 'variables': variables})
        jsonResponse = json.loads(r.text)
        return jsonResponse['data']['obtainKrakenToken']['token']
    except HTTPError as http_err:
        print(f'HTTP Error {http_err}')
        logger.error(f'HTTP Error {http_err}')
    except Exception as err:
        print(f'Another error occurred: {err}')
        logger.error(f'Another error occurred: {err}')




def mqttPublish(message):
    client1= paho.Client(mqttClientName)                           #create client object
    #client1.on_publish = on_publish                          #assign function to callback
    client1.connect(mqttBroker, mqttPort)                                 #establish connection
    ret= client1.publish(mqttTopic, message)                   #publish
    client1.disconnect()
    #print("Published")

def getObject():
    #Get Token
    authToken = refreshToken(apikey,accountNumber)
    retryCount = 3
    
    while retryCount >= 0:
        try:
            query = """
                query getData($input: String!) {
                    plannedDispatches(accountNumber: $input) {
                        startDt
                        endDt
                    }
                }
            """
            variables = {'input': accountNumber}
            headers={"Authorization": authToken}
            r = requests.post(url, json={'query': query , 'variables': variables, 'operationName': 'getData'},headers=headers)
           # print(r.text)
            return json.loads(r.text)['data']
        except HTTPError as http_err:
            logger.error(f'HTTP Error {http_err}')
            time.sleep(5)
            retryCount -= 1
            
        except Exception as err:
            logger.error(f'Unknown error occurred: {err}')
            time.sleep(5)
            retryCount -= 1

                


def getTimes():
    logger.debug("Starting GetTimes")
    object = getObject()
    dispatches = object['plannedDispatches']
    
    retryCount = 3
    while dispatches is None and retryCount >= 0:
        time.sleep(5)
        print("dispatches is none. retrying")
        object = getObject()
        retryCount -= 1
        
    if dispatches is None:
        #logger.error("Sorry, dispatches is still none")
        raise Exception("Sorry, dispatches is still none after 3 attempts.") 
      
        
    return dispatches

def returnPartnerSlotStart(startTime):
    for x in times:
        slotStart = datetime.strptime(x['startDt'],'%Y-%m-%d %H:%M:%S%z')
        slotEnd = datetime.strptime(x['endDt'],'%Y-%m-%d %H:%M:%S%z')
        if(startTime == slotEnd):
            return slotEnd

def returnPartnerSlotEnd(endTime):
    for x in times:
        slotStart = datetime.strptime(x['startDt'],'%Y-%m-%d %H:%M:%S%z')
        slotEnd = datetime.strptime(x['endDt'],'%Y-%m-%d %H:%M:%S%z')
        if(endTime == slotStart):
            return slotEnd

    

def dbInsert(SlotStart, SlotEnd, insertDate):
    try:
        conn  = pymysql.connect(host=DBHost, user=DBUser, password=DBPassword, database=DBDatabase)
        DBCurr  = conn.cursor()
        #insertDate = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = f"INSERT INTO ChargingSlots (SlotStart, SlotEnd, SlotAddedDt, hostname, tsStamp) VALUES ('{SlotStart}', '{SlotEnd}', '{insertDate}', '{hostname}', now())"
        DBCurr.execute(query)
        #print(f"{DBCurr.rowcount} details inserted")
        conn.commit()
        conn.close()
    except Exception as err:
        logger.error(f'Another error occurred: {err}')

def getData():
    logger.debug("Starting GetData")
    dateTimeToUse = datetime.now().astimezone()
    #if dateTimeToUse.hour < 17:
    #    dateTimeToUse = dateTimeToUse-timedelta(days=1)
    ioStart = dateTimeToUse.astimezone().replace(hour=23, minute=30, second=0, microsecond=0)
    ioEnd = dateTimeToUse.astimezone().replace(microsecond=0).replace(hour=5, minute=30, second=0, microsecond=0)+timedelta(days = 1)

    times = getTimes()
    #Convert to the current timezone
    for i,time in enumerate(times):
        slotStart = datetime.strptime(time['startDt'],'%Y-%m-%d %H:%M:%S%z').astimezone(ZoneInfo("Europe/London"))
        slotEnd = datetime.strptime(time['endDt'],'%Y-%m-%d %H:%M:%S%z').astimezone(ZoneInfo("Europe/London"))
        time['startDt'] = str(slotStart)
        time['endDt'] = str(slotEnd)
        times[i] = time

    timeNow = datetime.now(timezone.utc).astimezone()

    #Santise Times
    #Remove times within 23:30-05:30 slots
    newTimes = []
    addExtraSlot = True
    for i,time in enumerate(times):
        slotStart = datetime.strptime(time['startDt'],'%Y-%m-%d %H:%M:%S%z').astimezone()
        slotEnd = datetime.strptime(time['endDt'],'%Y-%m-%d %H:%M:%S%z').astimezone()
        if(not((ioStart <= slotStart <= ioEnd) and (ioStart <= slotEnd <= ioEnd))):
            if((slotStart <= ioStart) and (ioStart < slotEnd <= ioEnd)):
                time['endDt'] = str(ioStart)
                times[i] = time
            if((ioStart <= slotStart <= ioEnd) and (ioEnd < slotEnd)):
                time['startDt'] = str(ioEnd)
            newTimes.append(time)
        if((slotStart <= ioStart <= slotEnd) and (slotStart <= ioEnd <= slotEnd)):
            #This slot overlaps our IO slot - we need not add it manually at the next step
            addExtraSlot = False
    times = newTimes

    if(addExtraSlot):
        #Add our IO period
        ioPeriod = json.loads('[{"startDt": "'+str(ioStart)+'","endDt": "'+str(ioEnd)+'"}]')
        times.extend(ioPeriod)
        times.sort(key=lambda x: x['startDt'])

    newTimes = []
    #Any partner slots a.k.a. slots next to each other
    for i,time in enumerate(times):
        while True:
            slotStart = datetime.strptime(time['startDt'],'%Y-%m-%d %H:%M:%S%z').astimezone()
            slotEnd = datetime.strptime(time['endDt'],'%Y-%m-%d %H:%M:%S%z').astimezone()
            if((i+1)<len(times)):
                partnerStart = datetime.strptime(times[i+1]['startDt'],'%Y-%m-%d %H:%M:%S%z').astimezone()
                partnerEnd = datetime.strptime(times[i+1]['endDt'],'%Y-%m-%d %H:%M:%S%z').astimezone()
                if(slotEnd == partnerStart):
                    times.pop((i+1))
                    time['endDt'] = str(partnerEnd)
                    times[i] = time
                else:
                    break
            else:
                break

    newTimes = []
    #Any slots in the past
    for i,time in enumerate(times):
        slotStart = datetime.strptime(time['startDt'],'%Y-%m-%d %H:%M:%S%z').astimezone()
        slotEnd = datetime.strptime(time['endDt'],'%Y-%m-%d %H:%M:%S%z').astimezone()
        if(not(slotStart <= timeNow and slotEnd <= timeNow)):
            newTimes.append(time)
    times = newTimes

    # Check if our array is empty (everything may be in the past)
    if(len(times)==0):
        #print("IS EMPTY")
        times = json.loads('[{"startDt": "'+str(ioStart)+'","endDt": "'+str(ioEnd)+'"}]')

    nextRunStart = datetime.strptime(times[0]['startDt'],'%Y-%m-%d %H:%M:%S%z').astimezone()
    nextRunEnd = datetime.strptime(times[0]['endDt'],'%Y-%m-%d %H:%M:%S%z').astimezone()
    outputJson = {'nextRunStart':nextRunStart , 'nextRunEnd':nextRunEnd, 'timesObj': times, 'updatedAt': dateTimeToUse}
    outputJsonString = json.dumps(outputJson, indent=4, default=str)
    mqttPublish(outputJsonString)
    print(outputJsonString)
    dtNow = datetime.now()
    #print(dtNow.strftime('%Y-%m-%d %H:%M:%S'))
    for slots in outputJson['timesObj']:
        dtStart = datetime.strptime(slots['startDt'], '%Y-%m-%d %H:%M:%S%z')
        dtEnd = datetime.strptime(slots['endDt'], '%Y-%m-%d %H:%M:%S%z')
        #print(dtEnd.strftime('%Y-%m-%d %H:%M:%S'))
        #dbInsertDate = dateTimeToUse.strftime('%Y-%m-%d %H:%M:%S')
        
        dbInsert(SlotStart=dtStart.strftime('%Y-%m-%d %H:%M:%S'), SlotEnd=dtEnd.strftime('%Y-%m-%d %H:%M:%S'), insertDate=dateTimeToUse.strftime('%Y-%m-%d %H:%M:%S'))



def setDailySchedules():
    setMinuteSchedules()
    # schedule.every().day.at("13:00").do(setMinuteSchedules)
    # print("Daily Schedule: Set")
    
    # now = datetime.now()
    # current_time = now.strftime("%H:%M:%S")
    # start = '13:00:00'

    # if current_time > start:
        # print("set today's schedules too")
        # setMinuteSchedules()



def setMinuteSchedules():
    ##schedule.every(1).minutes.until(timedelta(hours=17)).do(getData) #run until 6am
    schedule.every(1).minutes.do(getData) #run until 6am
    logger.info("Minute schedule set")
    #print("Minute Schedule: Set")
   
def setSchedules():
    setDailySchedules()

if __name__ == '__main__':
    setSchedules()
    getData()

while True:
    try:
        schedule.run_pending()
    except:
        logger.error("Schedule runpending failed. Continuing")
    now = time.time()
    sd = int(now % 60)
    if(sd % 10 == 0):
        logger.debug(f"tick {sd}")
    time.sleep(1)