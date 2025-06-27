"""
Utility functions for chart generation and data processing.
"""
import json
import logging
from collections import defaultdict
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

def clean_key(key):
    """Clean up column names - remove quotes if present."""
    if isinstance(key, str):
        return key.strip('"\'')
    return key

def process_chart_data(data: List[Dict] or Any,
                       x_axis: str,
                       y_axis: str,
                       z_axis: Optional[str] = None) -> List[Dict]:
    """
    Process data into a format suitable for Highcharts.

    Parameters:
    - data: List[Dict] → the raw data to plot
    - x_axis: str → key in data to use as x-axis
    - y_axis: str → key in data to use as y-axis
    - z_axis: str or None → optional grouping key (e.g., series)

    Returns:
    - List of series data ready for Highcharts
    """
    # Clean up axis names
    x_axis = clean_key(x_axis)
    y_axis = clean_key(y_axis)
    z_axis = clean_key(z_axis) if z_axis else None

    logger.info(f"Processing chart data with x_axis={x_axis}, y_axis={y_axis}, z_axis={z_axis}")
    logger.info(f"Sample data: {data[:2] if isinstance(data, list) and len(data) > 0 else 'Empty or not a list'}")

    # Fallback to direct data usage if extracting from data items fails
    try:
        # If data is already in the right format for Highcharts
        if isinstance(data, list) and all(isinstance(item, (int, float)) for item in data):
            # Direct series data passed
            return [{"name": y_axis, "data": data}]
        elif isinstance(data, dict) and "series" in data:
            # Pre-formatted series data
            return data["series"]
        else:
            # Process data from objects
            series = defaultdict(list)

            # Check if data is a list of dictionaries with the expected keys
            if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                if z_axis:
                    for item in data:
                        if x_axis in item and y_axis in item and z_axis in item:
                            try:
                                x_val = item[x_axis]
                                y_val = float(item[y_axis]) if not isinstance(item[y_axis], (int, float)) else item[y_axis]
                                z_val = str(item[z_axis])
                                series[z_val].append([x_val, y_val])
                            except (ValueError, TypeError) as e:
                                logger.warning(f"Could not convert value: {e}")
                else:
                    # Use index numbers as X values if we're just plotting Y values
                    vehicle_ids = []
                    for item in data:
                        if y_axis in item:
                            try:
                                # Use device_name or ID as category if available
                                id_val = item.get('device_name', item.get('id', str(len(vehicle_ids))))
                                vehicle_ids.append(id_val)
                                y_val = float(item[y_axis]) if not isinstance(item[y_axis], (int, float)) else item[y_axis]
                                series["Series"].append([id_val, y_val])
                            except (ValueError, TypeError) as e:
                                logger.warning(f"Could not convert value: {e}")

                # Format series for Highcharts
                return [
                    {"name": name, "data": values}
                    for name, values in series.items()
                ]
            else:
                # Fallback for simple data
                logger.warning("Data format not recognized, using fallback series")
                series_data = [{"name": "Values", "data": []}]
                if isinstance(data, list) and all(isinstance(i, (int, float)) for i in data):
                    series_data[0]["data"] = [[i, val] for i, val in enumerate(data)]
                return series_data
    except Exception as e:
        logger.error(f"Error processing chart data: {e}")
        # Fallback to empty series with a clear error message
        return [{"name": "Error processing data", "data": []}]

def generate_highchart_html(data: List[Dict] or Any,
                          x_axis: str,
                          y_axis: str,
                          chart_config: Dict,
                          z_axis: Optional[str] = None,
                          chart_type: str = "column") -> str:
    """
    Generates a Highcharts HTML string from input data.

    Parameters:
    - data: List[Dict] → the raw data to plot
    - x_axis: str → key in data to use as x-axis
    - y_axis: str → key in data to use as y-axis
    - chart_config: Dict → configuration with HTML template and chart settings
    - z_axis: str or None → optional grouping key (e.g., series)
    - chart_type: str → type of Highcharts chart ("column", "line", "bar", etc.)
    """
    # Process chart data into series format
    series_data = process_chart_data(data, x_axis, y_axis, z_axis)

    # If we still have empty data, check if we can use the chart_config directly
    if (not series_data or not any(s.get("data") for s in series_data)) and hasattr(data, "highchart_config"):
        if "series" in data.highchart_config:
            series_data = data.highchart_config["series"]

    logger.info(f"Final series data: {series_data}")

    # Format the HTML template with the chart data
    html_template = chart_config.get("html_template", "")
    chart_title = chart_config.get("title", "Data Visualization")

    # Replace placeholders in the HTML template
    html = html_template.format(
        chart_type=chart_type,
        chart_title=chart_title,
        x_axis=x_axis,
        y_axis=y_axis,
        series_data=json.dumps(series_data)
    )

    return html

def generate_chart_from_config(chart_config: Dict) -> str:
    """
    Generate HTML chart directly from a complete chart configuration.

    Parameters:
    - chart_config: Dict → Complete Highcharts configuration

    Returns:
    - HTML string with embedded chart
    """
    try:
        # Remove any html_template key if it exists since we're generating our own
        clean_config = {k: v for k, v in chart_config.items() if k != 'html_template'}

        # Serialize the config to JSON with proper escaping
        config_json = json.dumps(clean_config, ensure_ascii=False, separators=(',', ':'))

        # Generate the HTML template with the properly serialized JSON
        html = f"""<!DOCTYPE html>
<html>
<head>
<title>Data Visualization</title>
<script src="https://code.highcharts.com/highcharts.js"></script>
</head>
<body>
<div id="container" style="width: 100%; height: 400px;"></div>
<script>
Highcharts.chart('container', {config_json});
</script>
</body>
</html>"""

        return html

    except Exception as e:
        logger.error(f"Error generating chart HTML: {e}")
        return f"""<!DOCTYPE html>
<html>
<head>
<title>Chart Error</title>
</head>
<body>
<div>Error generating chart: {str(e)}</div>
</body>
</html>"""
