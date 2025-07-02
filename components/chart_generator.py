"""Chart generation utility functions for Highcharts."""
import json
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def generate_highchart_config(chart_type: str, x_axis_column: str, y_axis_column: str,
                             x_axis_label: str, y_axis_label: str, chart_title: str,
                             json_data: str, z_axis_column: Optional[str] = None,
                             z_axis_label: Optional[str] = None) -> Dict:
    """
    Generate Highcharts configuration from chart parameters.

    Args:
        chart_type: Type of chart (column, line, pie, bar)
        x_axis_column: Column name for x-axis
        y_axis_column: Column name for y-axis
        x_axis_label: Label for x-axis
        y_axis_label: Label for y-axis
        chart_title: Title for the chart
        json_data: JSON string containing the data
        z_axis_column: Optional column for z-axis (for 3D charts)
        z_axis_label: Optional label for z-axis

    Returns:
        Dictionary containing Highcharts configuration
    """
    try:
        # Parse data
        data = json.loads(json_data) if isinstance(json_data, str) else json_data

        # Extract chart data from Elasticsearch results or direct data
        chart_data = []
        if isinstance(data, dict) and 'hits' in data and 'hits' in data['hits']:
            chart_data = [hit['_source'] for hit in data['hits']['hits'] if '_source' in hit]
        elif isinstance(data, list):
            chart_data = data

        if not chart_data:
            return {}

        # Prepare series data based on chart type
        if chart_type == "pie":
            series_data = []
            for item in chart_data:
                if x_axis_column in item and y_axis_column in item:
                    series_data.append({
                        'name': str(item[x_axis_column]),
                        'y': float(item[y_axis_column]) if isinstance(item[y_axis_column], (int, float)) else 1
                    })

            return {
                "chart": {"type": chart_type},
                "title": {"text": chart_title},
                "series": [{
                    "name": y_axis_label,
                    "data": series_data
                }]
            }
        else:
            # For column, line, bar charts
            categories = []
            series_data = []

            for item in chart_data:
                if x_axis_column in item and y_axis_column in item:
                    categories.append(str(item[x_axis_column]))
                    y_value = item[y_axis_column]
                    # Convert to number if possible
                    if isinstance(y_value, (int, float)):
                        series_data.append(y_value)
                    elif isinstance(y_value, str) and y_value.replace('.', '').replace('-', '').isdigit():
                        series_data.append(float(y_value))
                    else:
                        series_data.append(1)  # Default value

            return {
                "chart": {"type": chart_type},
                "title": {"text": chart_title},
                "xAxis": {
                    "categories": categories,
                    "title": {"text": x_axis_label}
                },
                "yAxis": {
                    "title": {"text": y_axis_label}
                },
                "series": [{
                    "name": y_axis_label,
                    "data": series_data
                }]
            }

    except Exception as e:
        logger.error(f"Error generating chart config: {e}")
        return {}
