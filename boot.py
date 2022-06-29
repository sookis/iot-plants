import network
from network import WLAN
import machine
import time
import pycom

pycom.heartbeat(False)
pycom.rgbled(0xffffff)


wlan = network.WLAN(mode=network.WLAN.STA)
wlan.connect('network ssid', auth=(network.WLAN.WPA2, 'password'))

print("Connecting to WLAN...")
while not wlan.isconnected():
    pycom.rgbled(0xaa0000)
    time.sleep(1)
print("We are connected to WiFi!")
print(wlan.ifconfig())
pycom.rgbled(0x00FF00)
