import keys
import board
import busio
import notecard
from adafruit_bme280 import basic as adafruit_bme280
import utils
import time
from time import sleep

productUID = keys.PRODUCT_UID

# initialize the Blues Wireless Notecard (blues.io)
i2c = busio.I2C(board.SCL, board.SDA)
card = notecard.OpenI2C(i2c, 0, 0, debug=True)

# create reference to BME280
bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c)
bme280.sea_level_pressure = 1013.25

lat_def = 43.05769554337394
lon_def = -89.5070545945101

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

                if "lat" in rsp and "lon" in rsp:
                    lat_def = rsp["lat"]
                    lon_def = rsp["lon"]

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

    # first get the updated sea level pressure
    sl_pressure = utils.get_sea_level_pressure(card, lat_def, lon_def)

    if sl_pressure <= 0:
        sl_pressure = 1013.25

    bme280.sea_level_pressure = sl_pressure
    sleep(1)

    note_body = {}

    # get 50 readings from the sensor and use the median values
    temp_list = []
    humidity_list = []
    pressure_list = []
    altitude_list = []

    for x in range(50):
        temp_list.append(bme280.temperature)
        humidity_list.append(bme280.relative_humidity)
        pressure_list.append(bme280.pressure)
        altitude_list.append(bme280.altitude)
        sleep(0.1)

    med_temp = utils.get_median(temp_list)
    med_humidity = utils.get_median(humidity_list)
    med_pressure = utils.get_median(pressure_list)
    med_altitude = utils.get_median(altitude_list)

    print("Temperature: %0.1f C" % med_temp)
    print("Humidity: %0.1f %%" % med_humidity)
    print("Pressure: %0.3f hPa" % med_pressure)
    print("Altitude = %0.2f meters" % med_altitude)
    print("Sea Level Pressure = %0.3f hPa" % sl_pressure)

    note_body["temperature"] = med_temp
    note_body["humidity"] = med_humidity
    note_body["pressure"] = med_pressure
    note_body["altitude"] = med_altitude
    note_body["sealevelpressure"] = sl_pressure

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
    sleep(60)
