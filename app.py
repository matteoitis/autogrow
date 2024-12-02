from flask import Flask, render_template, request, redirect, url_for, jsonify
import mysql.connector
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import RPi.GPIO as GPIO
import threading
import time

app = Flask(__name__)

# Initialize I2C and ADS1115
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)

# Define sensors and pumps
sensors = [AnalogIn(ads, ADS.P0), AnalogIn(ads, ADS.P1), AnalogIn(ads, ADS.P2), AnalogIn(ads, ADS.P3)]
pump_pins = [26, 19, 13, 6]
GPIO.setmode(GPIO.BCM)
for pin in pump_pins:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.HIGH)

# Database config
db_config = {
    "host": "localhost",
    "user": "pi",
    "password": "pi",
    "database": "pigrow"
}

# Thresholds, overrides, and modes
threshold_voltages = [1.5] * 4
manual_overrides = [False] * 4
current_modes = ["auto"] * 4

def read_sensor_data(sensor_id):
    while True:
        try:
            raw_data = sensors[sensor_id].value
            voltage = sensors[sensor_id].voltage
            with mysql.connector.connect(**db_config) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO soil (sensor_id, raw_data, voltage) VALUES (%s, %s, %s)",
                    (sensor_id, raw_data, voltage)
                )
                conn.commit()

            if not manual_overrides[sensor_id] and current_modes[sensor_id] == "auto":
                if voltage < threshold_voltages[sensor_id]:
                    GPIO.output(pump_pins[sensor_id], GPIO.LOW)
                else:
                    GPIO.output(pump_pins[sensor_id], GPIO.HIGH)
            time.sleep(1)
        except Exception as e:
            print(f"Sensor {sensor_id} error: {e}")

# Start threads for each sensor
for i in range(4):
    threading.Thread(target=read_sensor_data, args=(i,), daemon=True).start()

@app.route('/')
def index():
    with mysql.connector.connect(**db_config) as conn:
        cursor = conn.cursor(dictionary=True)
        latest_data = []
        for sensor_id in range(4):
            cursor.execute(
                "SELECT raw_data, voltage FROM soil WHERE sensor_id = %s ORDER BY id DESC LIMIT 1",
                (sensor_id,)
            )
            latest_data.append(cursor.fetchone() or {"raw_data": "N/A", "voltage": "N/A"})
    return render_template(
        'page.html',
        latest_data=latest_data,
        threshold_voltages=threshold_voltages,
        current_modes=current_modes,
        manual_overrides=manual_overrides
    )

@app.route('/control', methods=['POST'])
def control():
    sensor_id = int(request.form['sensor_id'])
    action = request.form['action']
    if action == 'on':
        manual_overrides[sensor_id] = True
        current_modes[sensor_id] = "manual"
        GPIO.output(pump_pins[sensor_id], GPIO.LOW)
    elif action == 'off':
        manual_overrides[sensor_id] = True
        current_modes[sensor_id] = "manual"
        GPIO.output(pump_pins[sensor_id], GPIO.HIGH)
    elif action == 'auto':
        manual_overrides[sensor_id] = False
        current_modes[sensor_id] = "auto"
    return redirect(url_for('index'))

@app.route('/set_threshold', methods=['POST'])
def set_threshold():
    sensor_id = int(request.form['sensor_id'])
    threshold_voltages[sensor_id] = float(request.form['threshold'])
    return redirect(url_for('index'))

@app.route('/data')
def data():
    with mysql.connector.connect(**db_config) as conn:
        cursor = conn.cursor(dictionary=True)
        data = []
        for sensor_id in range(4):
            cursor.execute(
                "SELECT raw_data, voltage FROM soil WHERE sensor_id = %s ORDER BY id DESC LIMIT 1",
                (sensor_id,)
            )
            data.append(cursor.fetchone() or {"raw_data": "N/A", "voltage": "N/A"})
    return jsonify(data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
