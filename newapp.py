from flask import Flask, render_template, request, redirect, url_for, jsonify
import os
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
threads = []  # Track sensor reading threads

# Safe read function with error handling
def safe_read(sensor):
    try:
        raw_data = sensor.value
        voltage = sensor.voltage
        return raw_data, voltage
    except Exception as e:
        print(f"Error reading sensor: {e}")
        return None, None

# Sensor reading function
def read_sensor_data(sensor_id):
    while True:
        try:
            raw_data, voltage = safe_read(sensors[sensor_id])
            
            if raw_data is not None and voltage is not None:
                # Log to database
                conn = mysql.connector.connect(**db_config)
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO soil (sensor_id, raw_data, voltage) VALUES (%s, %s, %s)",
                    (sensor_id, raw_data, voltage)
                )
                conn.commit()
                cursor.close()
                conn.close()

                # Auto mode logic: only control pumps when in auto mode
                if current_modes[sensor_id] == "auto" and not manual_overrides[sensor_id]:
                    if voltage > threshold_voltages[sensor_id]:
                        GPIO.output(pump_pins[sensor_id], GPIO.LOW)  # Activate pump
                    else:
                        GPIO.output(pump_pins[sensor_id], GPIO.HIGH)  # Deactivate pump

            time.sleep(2)  # Delay to avoid overloading the I2C bus
        except Exception as e:
            print(f"Sensor {sensor_id} error: {e}")

# Start threads for each sensor
def start_sensor_threads():
    global threads
    stop_sensor_threads()  # Stop any existing threads first
    threads = []
    for i in range(4):
        thread = threading.Thread(target=read_sensor_data, args=(i,))
        thread.daemon = True
        thread.start()
        threads.append(thread)

# Stop sensor reading threads
def stop_sensor_threads():
    global threads
    threads = []  # Clear the threads list, effectively stopping old threads

# Restart the entire program
@app.route('/restart_program', methods=['POST'])
def restart_program():
    os.execv(__file__, ["python3"] + os.sys.argv)

# Restart the sensor threads
@app.route('/restart_sensors', methods=['POST'])
def restart_sensors():
    start_sensor_threads()
    return redirect(url_for('index'))

# Flask routes
@app.route('/')
def index():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    latest_data = []
    for sensor_id in range(4):
        cursor.execute(
            "SELECT raw_data, voltage FROM soil WHERE sensor_id = %s ORDER BY id DESC LIMIT 1",
            (sensor_id,)
        )
        row = cursor.fetchone()
        latest_data.append(row or {"raw_data": "N/A", "voltage": "N/A"})
    cursor.close()
    conn.close()
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
    threshold = float(request.form['threshold'])
    threshold_voltages[sensor_id] = threshold
    return redirect(url_for('index'))

@app.route('/data')
def data():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        data = []
        for sensor_id in range(4):
            cursor.execute(
                "SELECT raw_data, voltage FROM soil WHERE sensor_id = %s ORDER BY id DESC LIMIT 1",
                (sensor_id,)
            )
            row = cursor.fetchone()
            sensor_data = row or {"raw_data": "N/A", "voltage": "N/A"}
            sensor_data["mode"] = current_modes[sensor_id]  # Add current mode
            sensor_data["threshold"] = threshold_voltages[sensor_id]  # Add threshold
            data.append(sensor_data)
        cursor.close()
        conn.close()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"Error: {e}"}), 500

if __name__ == '__main__':
    start_sensor_threads()  # Start sensor threads
    app.run(host='0.0.0.0', port=5000)
