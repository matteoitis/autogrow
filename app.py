from flask import Flask, render_template, request, redirect, url_for, jsonify
import mysql.connector
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import RPi.GPIO as GPIO
import threading
import time
from sensor import Sensor
from pump import Pump

app = Flask(__name__)

# Initialize the I2C interface
i2c = busio.I2C(board.SCL, board.SDA)

# Initialize the ADS1115 ADC
ads = ADS.ADS1115(i2c)

# Initialize sensors and pumps
sensors = [Sensor(ads, ADS.P0), Sensor(ads, ADS.P1), Sensor(ads, ADS.P2), Sensor(ads, ADS.P3)]
pumps = [Pump(26), Pump(19), Pump(13), Pump(6)]  # GPIO pins for pumps

# MariaDB connection details
db_config = {
    "host": "localhost",
    "user": "pi",
    "password": "pi",
    "database": "autogrow"
}

# Threshold values for when to turn the pumps on
threshold_voltages = [1.5, 1.5, 1.5, 1.5]

# Manual override flags
manual_overrides = [False, False, False, False]

# Current modes (auto or manual)
current_modes = ["auto", "auto", "auto", "auto"]

def read_sensor_data(sensor_id):
    global manual_overrides, current_modes
    while True:
        try:
            if sensors[sensor_id].is_connected():
                raw_value = sensors[sensor_id].read_raw_value()
                voltage_value = sensors[sensor_id].read_voltage()

                # Save data into MariaDB immediately for real-time access
                conn = mysql.connector.connect(**db_config)
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO soil (sensor_id, raw_data, voltage) VALUES (%s, %s, %s)",
                    (sensor_id, raw_value, voltage_value)
                )
                conn.commit()
                cursor.close()
                conn.close()

                print(f"Sensor {sensor_id} - Raw Data: {raw_value}, Voltage: {voltage_value}")

                if not manual_overrides[sensor_id]:
                    # Check if the voltage is above the threshold to control the pump
                    if voltage_value > threshold_voltages[sensor_id]:
                        pumps[sensor_id].on()
                        print(f"Pump {sensor_id} ON - Soil moisture low")
                    else:
                        pumps[sensor_id].off()
                        print(f"Pump {sensor_id} OFF - Soil moisture sufficient")

            else:
                print(f"Sensor {sensor_id} is not connected.")
            time.sleep(1)  # Additional delay before the next loop iteration

        except OSError as os_err:
            print(f"OS Error: {os_err}")
        except mysql.connector.Error as db_err:
            print(f"Database Error: {db_err}")
        except Exception as e:
            print(f"Error: {e}")

# Start the sensor reading in separate threads
for i in range(4):
    sensor_thread = threading.Thread(target=read_sensor_data, args=(i,))
    sensor_thread.daemon = True
    sensor_thread.start()

@app.route('/')
def index():
    try:
        # Connect to the database and fetch the latest data for each sensor
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        latest_data = []
        for sensor_id in range(4):
            cursor.execute("SELECT raw_data, voltage FROM soil WHERE sensor_id = %s ORDER BY id DESC LIMIT 1", (sensor_id,))
            latest_data.append(cursor.fetchone())
        cursor.close()
        conn.close()

        return render_template('page.html', latest_data=latest_data, threshold_voltages=threshold_voltages, current_modes=current_modes)
    except mysql.connector.Error as db_err:
        return f"Database Error: {db_err}"
    except Exception as e:
        return f"Error: {e}"

@app.route('/control', methods=['POST'])
def control():
    global manual_overrides, current_modes
    sensor_id = int(request.form.get('sensor_id'))
    action = request.form.get('action')
    if action == 'on':
        manual_overrides[sensor_id] = True
        current_modes[sensor_id] = "manual"
        pumps[sensor_id].on()
    elif action == 'off':
        manual_overrides[sensor_id] = True
        current_modes[sensor_id] = "manual"
        pumps[sensor_id].off()
    elif action == 'auto':
        manual_overrides[sensor_id] = False
        current_modes[sensor_id] = "auto"
    return redirect(url_for('index'))

@app.route('/set_threshold', methods=['POST'])
def set_threshold():
    global threshold_voltages
    sensor_id = int(request.form.get('sensor_id'))
    threshold_voltages[sensor_id] = float(request.form.get('threshold'))
    return redirect(url_for('index'))

@app.route('/data')
def data():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        data = []
        for sensor_id in range(4):
            cursor.execute("SELECT raw_data, voltage FROM soil WHERE sensor_id = %s ORDER BY id DESC LIMIT 1", (sensor_id,))
            data.append(cursor.fetchone())
        cursor.close()
        conn.close()

        return {"data": data}
    except mysql.connector.Error as db_err:
        return {"error": f"Database Error: {db_err}"}, 500
    except Exception as e:
        return {"error": f"Error: {e}"}, 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
