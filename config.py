import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


    ES_SCHEMA = """
    INDEX_SCHEMA = {
        "vehicle_summary_llm_chatbot": [
            "avg_speed", "center", "crash", "device_id", "device_name", "distance",
            "driving_safety_score", "driving_score", "end_lat", "end_lng", "end_odometer",
            "end_position_id", "end_time", "end_time_date", "end_time_time", "engine_2_seconds",
            "engine_seconds", "excessive_idle_seconds", "excessive_over_speed_seconds",
            "excessive_stop_seconds", "filter_positions_count", "final_penalty", "first_ignition_on",
            "first_position_time", "front", "frontLeft", "frontRight", "front_right_motor_time",
            "fuel_consumption", "geo_in_count", "geo_in_distance", "geo_in_end", "geo_in_seconds",
            "geo_out_count", "geo_out_distance", "geo_out_seconds", "harsh_acceleration",
            "harsh_acceleration_penalty", "harsh_braking", "harsh_braking_penalty", "harsh_cornering",
            "harsh_turn_penalty", "id", "idle_seconds", "ign_off_count", "ign_on_count",
            "ignition_records", "last_battery", "last_battery_level", "last_ignition_on",
            "last_position_time", "low_batt_counts", "low_fuel_counts", "max_speed",
            "max_speed_time", "more_events_penalty", "motion_records", "motion_seconds",
            "night_driving", "over_ignition", "over_motion", "over_speed", "over_speed_penalty",
            "over_speed_seconds", "penalty_list", "penalty_per_km", "power_cut_counts",
            "raw_positions_count", "server_id", "start_battery", "start_battery_level",
            "start_lat", "start_lng", "start_odometer", "start_position_id", "start_time",
            "start_time_date", "start_time_time", "steps", "stop_seconds", "summary_date",
            "utilization"
        ],
        "vehicle_stop_idle_reports": [
            "id", "server_id", "device_id", "device_name", "type", "engine_seconds",
            "start_time", "start_time_date", "start_time_time", "start_time_epoch",
            "end_time", "end_time_date", "end_time_time", "end_time_epoch",
            "lat", "lng", "stop_idle_date", "duration_seconds", "position_id",
            "timestamp_column1", "timestamp_column2"
        ],
        "vehicle_alarm_events": [
            "id", "type", "servertime", "servertime_date", "servertime_time", "servertime_epoch",
            "deviceid", "positionid", "geofenceid", "fixtime", "fixtime_date", "fixtime_time", "fixtime_epoch",
            "latitude", "longitude", "geofencename", "driver_id", "tag_id", "status", "alarm"
        ],
        "vehicle_trip_summary": [
            "id", "server_id", "device_id", "device_name", "distance", "avg_speed", "max_speed",
            "max_speed_time", "max_speed_time_date", "max_speed_time_time", "max_speed_time_epoch",
            "start_position_id", "end_position_id", "duration", "start_time", "start_time_date",
            "start_time_time", "start_time_epoch", "end_time", "end_time_date", "end_time_time",
            "end_time_epoch", "start_lat", "end_lat", "start_lng", "end_lng", "trip_date",
            "harsh_braking", "harsh_acceleration", "harsh_cornering", "utilization", "over_speed",
            "night_driving", "crash", "ignition_records", "motion_records",
            "excessive_idle_seconds", "excessive_over_speed_seconds", "driving_safety_score",
            "over_motion", "over_ignition", "start_battery_level", "end_battery_level",
            "start_battery", "end_battery", "power_start", "power_end", "power_difference",
            "start_odometer", "end_odometer", "start_voltage", "end_voltage", "start_soc",
            "end_soc", "motion_seconds", "idle_seconds"
        ],
    }
    """
    ES_INSTRUCTIONS = """
    Generate Elasticsearch queries using the provided schema.
    Use the following guidelines:
    - Use the index names as provided in the schema.
    - Use the fields listed in the schema for filtering, sorting, and aggregations.
    - Use the appropriate Elasticsearch query syntax (e.g., match, term, range).
    - Use the provided field names exactly as they are in the schema.
    - Use the correct data types for each field (e.g., date, keyword, float).
    """

    # Chart templates and configurations
    CHART_CONFIG = {
        "html_template": """
<!DOCTYPE html>
<html>
<head>
    <title>Data Visualization</title>
    <script src="https://code.highcharts.com/highcharts.js"></script>
</head>
<body>
<div id="container" style="width: 100%; height: 400px;"></div>
<script>
Highcharts.chart('container', {{
    chart: {{
        type: '{chart_type}'
    }},
    title: {{
        text: '{chart_title}'
    }},
    xAxis: {{
        type: 'category',
        title: {{
            text: '{x_axis}'
        }}
    }},
    yAxis: {{
        title: {{
            text: '{y_axis}'
        }}
    }},
    series: {series_data}
}});
</script>
</body>
</html>
""",
        "chart_config_template": """
<!DOCTYPE html>
<html>
<head>
    <title>Data Visualization</title>
    <script src="https://code.highcharts.com/highcharts.js"></script>
</head>
<body>
<div id="container" style="width: 100%; height: 400px;"></div>
<script>
Highcharts.chart('container', {chart_config});
</script>
</body>
</html>
"""
    }

settings = Settings()
