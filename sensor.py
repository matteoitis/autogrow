class Sensor:
    def __init__(self, i2c, pin):
        self.i2c = i2c
        self.pin = pin

    def read_raw_value(self):
        # Implement the logic to read raw value from the sensor
        return 0

    def read_voltage(self):
        # Implement the logic to convert raw value to voltage
        return 0.0
