import keys
import board
import busio
import notecard
import adafruit_bme680
import utils
import time
from time import sleep
#from machine import Pin

productUID = keys.PRODUCT_UID

# initialize the Blues Wireless Notecard (blues.io)
i2c = busio.I2C(board.SCL, board.SDA)
card = notecard.OpenI2C(i2c, 0, 0, debug=True)

# create reference to BME680
bme680 = adafruit_bme680.Adafruit_BME680_I2C(i2c, debug=False)
bme680.sea_level_pressure = 1013.25

# associate Notecard with a project on Notehub.io
req = {"req": "hub.set"}
req["product"] = productUID
req["mode"] = "periodic"
req["sn"] = "indoor-tracker"
rsp = card.Transaction(req)

# enable GPS module on Notecard
req = {"req": "card.location.mode"}
req["mode"] = "periodic"
rsp = card.Transaction(req)

# enable motion tracking on Notecard
req = {"req": "card.motion.mode"}
req["start"] = True
rsp = card.Transaction(req)


def check_motion():
    """ check for Notecard movement to see if we need to update its location """

    req = {"req": "card.motion"}
    rsp = card.Transaction(req)

    if "count" in rsp and rsp["count"] > 0:
        # movement detected since last check!

        using_gps = False
        using_wifi = False

        # attempt to ascertain the current gps location
        using_gps = get_gps_location()

        if using_gps is False:
            # gps location timed out, switch to wi-fi triangulation
            using_wifi = set_wifi_triangulation()

        # location (should be) updated for all outbound data
        # send readings from the sensor to the cloud
        send_sensor_data(using_gps, using_wifi)


def get_gps_location():
    """ attempt to ascertain the latest gps location """

    # override the Notecard and force GPS into continuous mode
    # this helps to get the GPS location ASAP (but is not power-friendly!)
    req = {"req": "card.location.mode"}
    req["mode"] = "continuous"
    rsp = card.Transaction(req)

    # get timestamp of the previous location data
    req = {"req": "card.location"}
    rsp = card.Transaction(req)

    if "time" in rsp:
        last_gps_time = rsp["time"]
    else:
        last_gps_time = 0

    # loop until we get a new GPS reading OR it times out
    # if it times out, switch to wifi triangulation

    start_time = time.monotonic()
    gps_timeout_sec = 100
    result = False

    while True:
        current_time = time.monotonic()
        elapsed_time = current_time - start_time

        print(str(elapsed_time) + " secs elapsed")

        if elapsed_time <= gps_timeout_sec:

            # get the latest GPS location time
            req = {"req": "card.location"}
            rsp = card.Transaction(req)

            this_gps_time = 0

            if "time" in rsp:
                this_gps_time = rsp["time"]

            if this_gps_time > last_gps_time:
                # got an updated gps location
                result = True
                break

            if "stop" in rsp:
                # internal GPS timeout
                result = False
                break

            sleep(2)

        else:
            # GPS timeout based on gps_timeout_sec value
            result = False
            break

    # reset Notecard GPS back to periodic mode for power savings
    req = {"req": "card.location.mode"}
    req["mode"] = "periodic"
    rsp = card.Transaction(req)

    return result


def set_wifi_triangulation():
    """ use the card.triangulate api to set the local wifi access points """

    req = {"req": "card.triangulate"}
    req["mode"] = "wifi"
    rsp = card.Transaction(req)

    all_wifi_aps = utils.get_wifi_access_points()

    print(all_wifi_aps)

    if len(all_wifi_aps) > 0:
        req = {"req": "card.triangulate"}
        req["text"] = all_wifi_aps + "\n"
        rsp = card.Transaction(req)
        return True
    else:
        return False


def send_sensor_data(using_gps, using_wifi):
    """ send sensor data to the cloud with the Notecard """

    note_body = {}

    # get 50 readings from the sensor and use the median values
    temp_list = []
    gas_list = []
    humidity_list = []
    pressure_list = []
    altitude_list = []

    for x in range(50):
        temp_list.append(bme680.temperature)
        gas_list.append(bme680.gas)
        humidity_list.append(bme680.relative_humidity)
        pressure_list.append(bme680.pressure)
        altitude_list.append(bme680.altitude)
        sleep(0.05)

    print("Temperature: %0.1f C" % utils.get_median(temp_list))
    print("Gas: %d ohm" % utils.get_median(gas_list))
    print("Humidity: %0.1f %%" % utils.get_median(humidity_list))
    print("Pressure: %0.3f hPa" % utils.get_median(pressure_list))
    print("Altitude = %0.2f meters" % utils.get_median(altitude_list))

    note_body["temperature"] = utils.get_median(temp_list)
    note_body["gas"] = utils.get_median(gas_list)
    note_body["humidity"] = utils.get_median(humidity_list)
    note_body["pressure"] = utils.get_median(pressure_list)
    note_body["altitude"] = utils.get_median(altitude_list)

    # get the battery voltage
    req = {"req": "card.voltage"}
    rsp = card.Transaction(req)
    note_body["voltage"] = rsp["value"]

    # get the wireless bars and rssi values
    req = {"req": "card.wireless"}
    rsp = card.Transaction(req)
    note_body["bars"] = rsp["net"]["bars"]
    note_body["rssi"] = rsp["net"]["rssi"]

    # deliver note to the notecard and sync immediately
    req = {"req": "note.add"}
    req["sync"] = True
    req["file"] = "indoor_tracker.qo"
    req["body"] = note_body
    rsp = card.Transaction(req)


while True:
    check_motion()
    sleep(10)
