"""Consolidated chart utilities - all chart functionality in one place."""
import json
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


def generate_chart_from_config(chart_config: Dict, container_id: str = "chartContainer") -> str:
    """
    Generate HTML for rendering a chart from Highcharts configuration.

    Args:
        chart_config: Highcharts configuration dictionary
        container_id: HTML element ID for the chart container

    Returns:
        HTML string for rendering the chart
    """
    try:
        if not chart_config:
            logger.warning("Empty chart config provided")
            return _generate_empty_chart_html(container_id)

        html_template = f"""<html>
                        <div id="{container_id}" style="width: 100%; height: 400px; margin: 20px 0;"></div>
                        <script src="https://code.highcharts.com/highcharts.js"></script>
                        <script src="https://code.highcharts.com/modules/exporting.js"></script>
                        <script>
                            document.addEventListener('DOMContentLoaded', function() {{
                                try {{
                                    Highcharts.chart('{container_id}', {json.dumps(chart_config, indent=2)});
                                }} catch (error) {{
                                    console.error('Error rendering chart:', error);
                                    document.getElementById('{container_id}').innerHTML = '<p style="text-align: center; color: #666;">Error rendering chart</p>';
                                }}
                            }});
                        </script>
                        </html>
                        """
        logger.info(f"Generated chart HTML for container: {container_id}")
        return html_template

    except Exception as e:
        logger.error(f"Error generating chart HTML: {e}")
        return _generate_empty_chart_html(container_id, f"Error: {str(e)}")


def _generate_empty_chart_html(container_id: str = "chartContainer", message: str = "No data available") -> str:
    """Generate HTML for an empty chart placeholder."""
    return f"""
<div id="{container_id}" style="width: 100%; height: 400px; margin: 20px 0; 
     border: 2px dashed #ccc; display: flex; align-items: center; justify-content: center;">
    <p style="text-align: center; color: #666; font-size: 16px;">{message}</p>
</div>
"""


def auto_detect_columns(chart_data: List[Dict]) -> tuple[str, str]:
    """Auto-detect suitable columns for X and Y axes."""
    if not chart_data:
        return 'category', 'value'

    sample_item = chart_data[0]
    available_keys = list(sample_item.keys())

    # Look for common identifier columns for X-axis
    x_candidates = ['device_name', 'name', 'id', 'device_id', 'title', 'label']
    x_column = None
    for candidate in x_candidates:
        if candidate in available_keys:
            x_column = candidate
            break

    # If no common identifier found, use first string column
    if not x_column:
        for key in available_keys:
            if isinstance(sample_item[key], str):
                x_column = key
                break

    # Look for common numeric columns for Y-axis
    y_candidates = ['max_speed', 'speed', 'distance', 'value', 'count', 'amount', 'score']
    y_column = None
    for candidate in y_candidates:
        if candidate in available_keys:
            try:
                float(sample_item[candidate])
                y_column = candidate
                break
            except (ValueError, TypeError):
                continue

    # If no common numeric column found, use first numeric column
    if not y_column:
        for key in available_keys:
            try:
                float(sample_item[key])
                y_column = key
                break
            except (ValueError, TypeError):
                continue

    # Final fallbacks
    x_column = x_column or available_keys[0] if available_keys else 'category'
    y_column = y_column or (
        available_keys[1] if len(available_keys) > 1 else available_keys[0]) if available_keys else 'value'

    return x_column, y_column
