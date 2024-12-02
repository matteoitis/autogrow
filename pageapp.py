<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Multi-Sensor Dashboard</title>
    <script>
        function fetchSensorData() {
            fetch('/data')
                .then(response => response.json())
                .then(data => {
                    data.forEach((sensor, index) => {
                        document.getElementById(`raw_data_${index}`).textContent = sensor.raw_data || "N/A";
                        document.getElementById(`voltage_${index}`).textContent = sensor.voltage || "N/A";
                        document.getElementById(`mode_${index}`).textContent = sensor.mode || "N/A";
                        document.getElementById(`threshold_${index}`).textContent = sensor.threshold || "N/A";
                    });
                })
                .catch(error => console.error('Error fetching data:', error));
        }

        setInterval(fetchSensorData, 2000); // Refresh every 2 seconds
    </script>
</head>
<body>
    <h1>Multi-Sensor Dashboard</h1>

    <button onclick="document.getElementById('restartSensorsForm').submit();">Restart Sensors</button>
    <button onclick="document.getElementById('restartProgramForm').submit();">Restart Program</button>

    <form id="restartSensorsForm" method="post" action="/restart_sensors" style="display:none;"></form>
    <form id="restartProgramForm" method="post" action="/restart_program" style="display:none;"></form>

    {% for sensor_id in range(4) %}
    <div>
        <h2>Sensor {{ sensor_id + 1 }}</h2>
        <p>Raw Data: <span id="raw_data_{{ sensor_id }}">Loading...</span></p>
        <p>Voltage: <span id="voltage_{{ sensor_id }}">Loading...</span></p>
        <p>Mode: <span id="mode_{{ sensor_id }}">Loading...</span></p>
        <p>Threshold: <span id="threshold_{{ sensor_id }}">Loading...</span></p>
        <form method="post" action="{{ url_for('control') }}">
            <input type="hidden" name="sensor_id" value="{{ sensor_id }}">
            <button type="submit" name="action" value="on">Turn Pump On</button>
            <button type="submit" name="action" value="off">Turn Pump Off</button>
            <button type="submit" name="action" value="auto">Auto Mode</button>
        </form>
        <form method="post" action="{{ url_for('set_threshold') }}">
            <input type="hidden" name="sensor_id" value="{{ sensor_id }}">
            <label>Threshold: <input type="number" step="0.1" name="threshold" value="{{ threshold_voltages[sensor_id] }}"></label>
            <button type="submit">Set Threshold</button>
        </form>
    </div>
    {% endfor %}
</body>
</html>