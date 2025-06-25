import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    # Fabric database settings
    FABRIC_SERVER = os.getenv("FABRIC_SERVER", "")
    FABRIC_DATABASE = os.getenv("FABRIC_DATABASE", "")
    FABRIC_CLIENT_ID = os.getenv("FABRIC_CLIENT_ID", "")
    FABRIC_CLIENT_SECRET = os.getenv("FABRIC_CLIENT_SECRET", "")
    FABRIC_TENANT_ID = os.getenv("FABRIC_TENANT_ID", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # Database Schema
    DATABASE_SCHEMA = """
    You're working with the following Microsoft Fabric SQL Server tables:

    1. f_invdata_with_code: Invoice data for projects across divisions
       - Key columns: invdatakey (PK), date, client, project_code, project_description, 
         region, country, division, budget_account_code, resource_name, invoice_amount_in_base_currency
       - Additional: client_code, entity, budget_account_description, sale_type, contract_type,
         emp_id, invoice_amount_in_tran_currency, currency, exchange_rate, _etldate, voucher_,
         etlactiveind, etljobname, envsourcecd, datasourcecd, etlcreateddatetime, etlupdateddatetime

    2. f_budgetdata_with_code: Budget allocations by division and category
       - Key columns: budgetdatakey (PK), dateperiod, division, budget_account_code, 
         budget_ledger_name, category, amount_in_usd, amount_in_inr
       - Additional: oh_type, conversion_rate, _etldate, etlactiveind, etljobname,
         envsourcecd, datasourcecd, etlcreateddatetime, etlupdateddatetime

    Relationships:
    - Join tables using budget_account_code only if required
    - Both tables have division column for filtering/grouping

    Notes:
    - Use LOWER() for case-insensitive string matches
    - Use LIKE with % for partial matches
    - current_date function not available
    """

    SQL_INSTRUCTIONS = """ Generate and execute T-SQL queries compatible with Microsoft Fabric SQL Warehouse. 
        Assume tables are accessed via ODBC and data is stored in Delta Lake format. 
        Use only supported features: SELECT, JOIN, GROUP BY, ORDER BY, CTEs, and WHERE clauses. 
        Avoid using stored procedures, variables, procedural blocks (BEGIN...END), or dynamic SQL. 
        For pagination, use OFFSET ... FETCH NEXT syntax. Always include an ORDER BY clause. Example: 
        'ORDER BY column OFFSET 0 ROWS FETCH NEXT 100 ROWS ONLY'. 
        Do not use LIMIT, as it is not supported in T-SQL. 
        For string matching: 
        1. Use LOWER() on both column and input for case-insensitive comparisons. 
        2. Use LIKE with % wildcards for partial matches. 
        3. Convert spaces in user input to % for fuzzy matching (e.g., 'E commerce' → LOWER(column) LIKE '%e%commerce%'). 
        4. Do not normalize, correct spelling, or change punctuation in user input (e.g., hyphens, quotes). 
        When generating the SQL query string, use alias for every column in the SELECT statement. 
        Do not include newline characters or unescaped quotes that could break JSON parsing. 
        Prefer single-line SQL strings do not use multi-line strings and do not format the answer give plain string without any formatting. """


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
