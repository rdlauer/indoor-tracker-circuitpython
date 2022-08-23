import wifi
import binascii
import keys
from time import sleep


def get_wifi_access_points():
    """ returns a set of visible access points, corresponds to esp32 AT+CWLAP format """
    # https://docs.espressif.com/projects/esp-at/en/latest/esp32/AT_Command_Set/Wi-Fi_AT_Commands.html#cmd-lap

    all_wifi_aps = ""

    for network in wifi.radio.start_scanning_networks():

        wifi_ap = "+CWLAP:("

        if wifi.AuthMode.ENTERPRISE in network.authmode:
            wifi_ap += "5"
        elif wifi.AuthMode.PSK in network.authmode:
            wifi_ap += "6"
        elif wifi.AuthMode.WPA3 in network.authmode:
            wifi_ap += "6"
        elif wifi.AuthMode.WPA2 in network.authmode:
            wifi_ap += "3"
        elif wifi.AuthMode.WPA in network.authmode:
            wifi_ap += "2"
        elif wifi.AuthMode.WEP in network.authmode:
            wifi_ap += "1"
        else:
            wifi_ap += "0"

        bssid = binascii.hexlify(network.bssid).decode("ascii")
        bssid = ':'.join(bssid[i:i+2] for i in range(0, 12, 2))

        wifi_ap = wifi_ap + ",\"" + str(network.ssid) + "\"," + str(
            network.rssi) + ",\"" + bssid + "\"," + str(network.channel) + ")\n"

        all_wifi_aps += wifi_ap

    wifi.radio.stop_scanning_networks()

    return all_wifi_aps


def get_median(ls):
    """ returns the median from a list """
    # sort the list
    ls_sorted = ls.sort()
    # find the median
    if len(ls) % 2 != 0:
        # total number of values are odd
        # subtract 1 since indexing starts at 0
        m = int((len(ls)+1)/2 - 1)
        return ls[m]
    else:
        m1 = int(len(ls)/2 - 1)
        m2 = int(len(ls)/2)
        return (ls[m1]+ls[m2])/2


def get_sea_level_pressure(card, lat, lon):
    """ get the sea level pressure from openweather api """

    # temporarily set notecard into continuous mode for a web transaction
    req = {"req": "hub.set"}
    req["on"] = True
    card.Transaction(req)

    # connect notecard to notehub
    req = {"req": "hub.sync"}
    card.Transaction(req)

    connectedToNotehub = False

    while not connectedToNotehub:
        req = {"req": "hub.status"}
        rsp = card.Transaction(req)

        if "connected" in rsp:
            connectedToNotehub = True
        else:
            sleep(1)

    # call openweather api to get latest pressure reading
    weatherURL = "/weather?lat=" + \
        str(lat) + "&lon=" + str(lon) + "&appid=" + keys.WEATHER_API_KEY

    req = {"req": "web.get"}
    req["route"] = "GetWeather"
    req["name"] = weatherURL
    rsp = card.Transaction(req)

    pressure = 0

    if rsp and "body" in rsp and "main" in rsp["body"] and "pressure" in rsp["body"]["main"]:
        pressure = rsp["body"]["main"]["pressure"]

    # set notecard back to periodic mode
    req = {"req": "hub.set"}
    req["off"] = True
    card.Transaction(req)

    return pressure
