from adafruit_ads1x15.analog_in import AnalogIn

class Sensor:
    def __init__(self, ads, pin):
        self.sensor_channel = AnalogIn(ads, pin)

    def read_raw_value(self):
        return self.sensor_channel.value

    def read_voltage(self):
        return self.sensor_channel.voltage
