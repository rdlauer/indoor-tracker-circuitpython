import wifi
import binascii


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
