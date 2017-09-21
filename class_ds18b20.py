#!/usr/bin/env python
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import json
import ast
import datetime
import time
import netifaces
import sys
import os  # for sensor
import glob #for sensor

# deactivation=False
MY_ID = 2167419
global MODEL
MODEL = 'DS18B20'
global deactivation
deactivation = False
global loopWorking
loopWorking = True
global edgeIP
edgeIP = 'fe80::ccee:14v1:n775:5158/64'
#sensor initialization
os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')

base_dir = '/sys/bus/w1/devices/'
device_folder = glob.glob(base_dir + '28*')[0]
device_file = device_folder + '/w1_slave'
#sensor initialization over

class Device():
    def __init__(self):
        # obtain the ip address
        addrswlan0 = netifaces.ifaddresses('wlan0')
        self.deviceIP = addrswlan0[netifaces.AF_INET][0]['addr']
        # obtain the 6lowpan address
        addrslowpan0 = netifaces.ifaddresses('lowpan0')
        self.deviceLowPanIP = addrslowpan0[netifaces.AF_INET6][1]['addr']

    def device_registration(self):
        # publish a registration message at first run

        try:
            with open('/home/pi/Desktop/JSONregistration.json', 'r') as f:
                json_data = json.load(f)
            f.close()
	    topic = json_data['Type']+'/'+str(MY_ID)
            json_data['Content']['Connectivity']['DeviceIP'] = self.deviceIP
	    json_data['Content']['GeneralDescription']['Model'] = str(MODEL)
            json_data['Content']['ID'] = str(MY_ID)
            json_data['Content']['Connectivity']['lowpanIP'] = self.deviceLowPanIP
            json_data['Content']['GeneralDescription']['DeploymentDate'] = datetime.datetime.fromtimestamp(
                time.time()).strftime(
                '%Y-%m-%d %H:%M:%S')
            publish.single(topic, "{}".format(json.dumps(json_data)), hostname=edgeIP)
            print "registration message is sent"
        except Exception as e:
            raise

    def output(self):
        f = open(device_file, 'r')
        lines = f.readlines()
        f.close()
        while lines[0].strip()[-3:] != 'YES':
            time.sleep(0.2)
            lines = read_temp_raw()
        equals_pos = lines[1].find('t=')
        if equals_pos != -1:
            temp_string = lines[1][equals_pos+2:]
            temp_c = float(temp_string) / 1000.0
            #temp_f = temp_c * 9.0 / 5.0 + 32.0
            return temp_c

class ClientSubscriber(mqtt.Client):
    def __init__(self):
        super(ClientSubscriber, self).__init__()
        print "subscriber is activated..."

    def on_connect(self, client, obj, flags, rc):
        self.subscribe(
            [("Output/#", 0), ("Registration/#", 0), ("Update/#", 0), ("Removal/#", 0), ("KeepAlive/#", 0),
             ("Deactivation/#", 0)])

    def on_message(self, client, obj, msg):
        print(msg.topic + " " + str(msg.payload))
        rawInput = json.loads(str(msg.payload), 'utf-8')
        # learn if message sent to this node
        if rawInput['Content']['ID'] == str(MY_ID):
            print "The message topic is being analyzed"
            # if message is about KeepAlive
            if msg.topic == "KeepAlive/":
                print "A KeepAlive message is detected"
                cf = device.output()
                # open the keepAlive.json file
                with open('/home/pi/Desktop/JSONKeepAlive.json', 'r+') as f:
                    json_data = json.load(f)
                f.close()
                # save the timestamp
		topic = json_data['Type']+'/'+str(MY_ID)
                json_data['Content']['AliveDate'] = datetime.datetime.fromtimestamp(time.time()).strftime(
                    '%Y-%m-%d %H:%M:%S')
                json_data['Content']['Output'] = str(cf)
                json_data['Content']['ID'] = str(MY_ID)
                # json_data=json.dumps(json_data)
                # print json_data
                # if keepAlive message comes send an answer
                publish.single(topic, "{}".format(json.dumps(json_data)), hostname=edgeIP)
                global deactivation
                deactivation = False
                print "keep alive message is sent back"

                # if message is about Deactivation
            elif msg.topic == "Deactivation/":
                print "A Deactivation message is detected"
                # open the deactivation.json file
                with open('/home/pi/Desktop/JSONdeactivation.json', 'r+') as f:
                    json_data = json.load(f)
                f.close()
                # save the timestamp
		topic = json_data['Type']+'/'+str(MY_ID)
                json_data["Content"]["DeactDate"] = datetime.datetime.fromtimestamp(time.time()).strftime(
                    '%Y-%m-%d %H:%M:%S')
                json_data['Content']['ID'] = str(MY_ID)
                # if deactivation message comes send an answer
                publish.single(topic, "{}".format(json.dumps(json_data)), hostname=edgeIP)
                global deactivation
                deactivation = True
                print "deactivation message is sent back. Device does not measure anymore, however, listens for messages."

                # if message is about Removal
            elif msg.topic == "Removal/":
                print "A Removal message is detected"
                # open the keepAlive.json file
                with open('/home/pi/Desktop/JSONremoval.json', 'r+') as f:
                    json_data = json.load(f)
                f.close()
		topic = json_data['Type']+'/'+str(MY_ID)
                json_data['Content']['ID'] = str(MY_ID)
                # save the timestamp
                # json_data["Content"]["Date"] = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
                # if keepAlive message comes send an answer
                publish.single(topic, "{}".format(json.dumps(json_data)), hostname=edgeIP)
                print "removal message is sent back"
                global loopWorking
                loopWorking = False
                #print str(loopWorking)

    def run(self):

        self.connect("localhost", 1883, 60)
        self.rc = 0
        former = -45
        while self.rc == 0 and loopWorking:
	    self.rc = self.loop()
            if deactivation == False:
                # can be filled
                cf = device.output()
		print cf
                # test if temperature has changed by 1% since last data transfer
                if abs(cf - former) >= (cf / 30):
                    with open('/home/pi/Desktop/JSONoutput.json', 'r+') as f:
                        json_data = json.load(f)
                    f.close()
		    topic = json_data['Type']+'/'+str(MY_ID)
                    json_data['Content']['Output'] = str(cf)
                    json_data['Content']['ID'] = str(MY_ID)
                    publish.single(topic, "{}".format(json.dumps(json_data)), hostname=edgeIP)
                    former = cf
            time.sleep(5)
        return self.rc

device = Device()
device.device_registration()

# run subscriber
mqttc = ClientSubscriber()
rc = mqttc.run()

if loopWorking:
    print "Device is removed by IoT Gateway!"
    sys.exit(0)
elif rc != 0:
    print "Mqtt could not be successfully executed!"
    sys.exit(0)
else:
    print "Mqtt is stopped for some reason..."
    sys.exit(0)


