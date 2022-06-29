from mqtt import MQTTClient
from LTR329ALS01 import LTR329ALS01
import SSD1306
from SI7006A20 import SI7006A20
from MPL3115A2 import MPL3115A2, ALTITUDE, PRESSURE
import time
from machine import Pin, I2C, ADC
from pycoproc_2 import Pycoproc
from dht import DHT  # https://github.com/JurassicPork/DHT_PyCom
import pycom

pycom.heartbeat(False)
pycom.rgbled(0x880088)

#  Pin setup
dht_pin = 'P23'             # Pin for Temp and Humidity
ADC_PIN = 'P16'             # Pin for moisture sensor
light_sensor_pin = 'P13'    # Pin for the light sensor
moist_control_pin = 'P11'   # Pin for controlling the moist sensor
rotary_dt = 'P3'                   # Pin for dt on Rotary encoder
rotary_clk = 'P4'                  # Pin for clk on Rotary encoder

# initialize the moist control pin and make it an output
moist_control = Pin(moist_control_pin, mode=Pin.OUT, pull=Pin.PULL_DOWN)
moist_control.value(0)  # Turn it off


# Make all Rotary encoder pins inputs
rotary_dt_pin = Pin(rotary_dt, mode=Pin.IN)
rotary_clk_pin = Pin(rotary_clk, mode=Pin.IN)

th = DHT(Pin(dht_pin, mode=Pin.OPEN_DRAIN), 0)  # Type 0 = dht11, which is what we have


# I2C
i2c = I2C(0)
i2c = I2C(0, I2C.MASTER)
i2c = I2C(0, pins=('P22', 'P21'))  # create and use the pins P22 and P21
i2c.init(I2C.MASTER, baudrate=40000)  # init as a master

py = Pycoproc()
if py.read_product_id() != Pycoproc.USB_PID_PYSENSE:
    raise Exception('Not a Pysense')

# Pysense sensors
si = SI7006A20(py)
lt = LTR329ALS01(py)
mpp = MPL3115A2(py, mode=PRESSURE)  # Returns pressure in Pa. Mode may also be set to ALTITUDE, returning a value in meters
mp = MPL3115A2(py, mode=ALTITUDE)  # Returns height in meters. Mode may also be set to PRESSURE, returning a value in Pascals

# OLED
OLED_WIDTH = 128
OLED_HEIGHT = 64

# initalize the ssd1306 oled screen
oled = SSD1306.SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c)
black = 0x000000

# Rotary encoder
last_status = (rotary_clk_pin() << 1) | rotary_dt_pin()  # Needed for Removal of duplicate values when turning the rotary encoder


counter = 0  # Keeps track of how many turns the rotary encoder makes.

# Nested dictionary with values for each plant
plant_dict = {"Tomat": {"max_moist": 65, "min_moist": 30},
              "Pelargon": {"max_moist": 75, "min_moist": 40},
              "Gurka": {"max_moist": 65, "min_moist": 30},
              "Palletblad": {"max_moist": 70, "min_moist": 40}
              }
# A list of the keys (Plant names) to present in the display
plants_list = list(plant_dict.keys())


def clear_oled(oled):
    oled.fill_rect(0, 0, OLED_WIDTH, OLED_HEIGHT, black)


def moist_result():
    if moist_control.value() == 1:
        time.sleep(2)
        moist_result = moist_sensor(ADC_PIN)     # Grabs the sensor value
        moisture = ((moist_result / 4096) * 100)
    else:
        moist_control.value(1)
        time.sleep(2)
        moist_result = moist_sensor(ADC_PIN)     # Grabs the sensor value
        moisture = ((moist_result / 4096) * 100)
    moist_control.value(0)
    return moisture


def plant_values(plant):
    global plant_dict, plant_list
    # Values
    values = plant_dict[plant]
    max_moist = (values["max_moist"])
    min_moist = (values["min_moist"])
    return max_moist, min_moist


def moist_sensor(pin):
    adc = ADC(bits=12)             # ADC used to read data
    apin = adc.channel(pin=pin, attn=ADC.ATTN_11DB)
    value = apin.value()
    return value


def show_plant_oled(counter):
    clear_oled(oled)
    oled.text(str(plants_list[counter]), 0, 0)
    oled.show()
    result = (moist_result())
    show_status_oled(counter, result)


def show_status_oled(counter, value):
    choice = plants_list[counter]
    min = plant_values(choice)[0]
    max = plant_values(choice)[1]
    value = round(value)
    oled.fill_rect(0, 50, 128, 64, black)
    if value > min:
        oled.text("Too Dry! (" + str(value) + "%)", 0, 50)
        time.sleep(0.5)
        pycom.rgbled(0x440000)
    elif value < max:
        oled.text("To Wet! (" + str(value) + "%)", 0, 50)
        time.sleep(0.5)
        pycom.rgbled(0x000044)
    else:
        oled.text("Perfect! (" + str(value) + "%)", 0, 50)
        time.sleep(0.5)
        pycom.rgbled(0x004400)
    oled.show()


def rotary_change(pin):
    global last_status, counter, plants_list, moisture
    max_counter = len(plants_list) - 1  # Make sure the counter never exceeds the number of plants
    new_status = (rotary_clk_pin() << 1) | rotary_dt_pin()
    if new_status == last_status:
        return
    transition = (last_status << 2) | new_status

    if transition == 0b1011 or transition == 0b0100:
        counter += 1
        if counter > max_counter:
            counter = 0
        show_plant_oled(counter)
    elif transition == 0b0111 or transition == 0b1000:
        counter -= 1
        if counter < 0:
            counter = max_counter
        show_plant_oled(counter)  # Refresh the display to show the selected plant.
    last_status = new_status


def blink_led():
    for n in range(1):
        pycom.rgbled(0x330033)
        time.sleep(0.5)
        pycom.rgbled(0x000000)
        time.sleep(0.2)


# MQTT SETUP
def sub_cb(topic, msg):
    print(msg)


mqtt_client = "mqtt-ip"
mqtt_user = 'mqtt-user'
mqtt_client_id = '1'

client = MQTTClient(mqtt_client_id, mqtt_client, user='mqtt-user', password="mqtt-password", port=1883)
client.set_callback(sub_cb)
client.connect()
client.subscribe(topic="devices/plant/control")

# Configure interupts for the rotary encoder
rotary_dt_pin.callback(Pin.IRQ_FALLING | Pin.IRQ_RISING, rotary_change)
rotary_clk_pin.callback(Pin.IRQ_FALLING | Pin.IRQ_RISING, rotary_change)

while True:
    result = th.read()
    while not result.is_valid():
        time.sleep(.5)
        result = th.read()
    moist_control.value(1)  # Turn on moisture sensor
    time.sleep(1)
    moisture = moist_result()
    moist_control.value(0)  # Turn off moisture sensor

# Send to mqtt in json format.
    client.publish(topic="devices/plant", msg='{"plant_sensor": {"temp":' + str(result.temperature) +
                          ',"rh":' + str(result.humidity) +
                          ',"Moisture":' + str(moisture) +
                          ',"Light":' + str(lt.lux()) +
                          '}}')
    print('Sensor data sent!')
    blink_led()
    time.sleep(1)
    show_status_oled(counter, moisture)
    time.sleep(1800)  # Sleep for 30 minutes
"""
Print to terminal for testing purposes
    print("MPL3115A2 temperature: " + str(mp.temperature()))
    print("Altitude: " + str(mp.altitude()))
    print("Pressure: " + str(mpp.pressure()))
    print('Temperature:', result.temperature)
    print('Humidity:', result.humidity)
    print("Light (channel Blue, channel Red): " + str(lt.light())," Lux: ", str(lt.lux()), "lx")
    print("Jordfuktighet: " + str(moisture))
    print("Temperature: " + str(si.temperature())+ " deg C and Relative Humidity: " + str(si.humidity()) + " %RH")
    print("Dew point: "+ str(si.dew_point()) + " deg C")
    t_ambient = 24.4
    print("Humidity Ambient for " + str(t_ambient) + " deg C is " + str(si.humid_ambient(t_ambient)) + "%RH")
"""

