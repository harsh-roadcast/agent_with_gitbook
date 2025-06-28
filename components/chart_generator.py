"""Chart generation implementation using DSPy - cleaned up version."""
import json
import logging
from typing import Dict, Optional, List, Tuple

from core.interfaces import IChartGenerator
from util.chart_utils import generate_chart_from_config, auto_detect_columns

logger = logging.getLogger(__name__)


class DSPyChartGenerator(IChartGenerator):
    """DSPy-based chart generator implementation."""

    def __init__(self, default_chart_type: str = "column"):
        """Initialize the chart generator with default chart type."""
        self.default_chart_type = default_chart_type

    def generate_chart(self, data: Dict, user_query: str, conversation_history: Optional[List[Dict]] = None) -> Tuple[Optional[Dict], Optional[str]]:
        """Generate chart configuration and HTML."""
        try:
            # Convert data to JSON string for processing
            json_data = json.dumps(data) if not isinstance(data, str) else data

            # Auto-detect chart parameters from data and query
            chart_params = self._detect_chart_parameters(json_data, user_query)

            if not chart_params:
                return None, None

            # Generate chart configuration
            chart_config = generate_highchart_config(**chart_params, json_data=json_data)

            # Generate HTML
            chart_html = generate_chart_from_config(chart_config)

            return chart_config, chart_html

        except Exception as e:
            logger.error(f"Error generating chart: {e}")
            return None, None

    async def generate_chart_async(self, data: Dict, user_query: str, conversation_history: Optional[List[Dict]] = None) -> Tuple[Optional[Dict], Optional[str]]:
        """Generate chart asynchronously."""
        # For now, delegate to synchronous method
        return self.generate_chart(data, user_query, conversation_history)

    def _detect_chart_parameters(self, json_data: str, user_query: str) -> Optional[Dict]:
        """Detect chart parameters from data and query."""
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
                return None

            # Auto-detect columns
            columns = auto_detect_columns(chart_data)
            if not columns:
                return None

            # Simple heuristics for chart type and axes
            chart_type = self.default_chart_type  # Use instance default
            if "line" in user_query.lower() or "trend" in user_query.lower():
                chart_type = "line"
            elif "pie" in user_query.lower():
                chart_type = "pie"
            elif "bar" in user_query.lower():
                chart_type = "bar"

            # Use first two suitable columns
            x_axis_column = columns[0] if len(columns) > 0 else ""
            y_axis_column = columns[1] if len(columns) > 1 else columns[0]

            return {
                "chart_type": chart_type,
                "x_axis_column": x_axis_column,
                "y_axis_column": y_axis_column,
                "x_axis_label": x_axis_column.title(),
                "y_axis_label": y_axis_column.title(),
                "chart_title": f"Chart: {user_query[:50]}...",
                "z_axis_column": None,
                "z_axis_label": None
            }

        except Exception as e:
            logger.error(f"Error detecting chart parameters: {e}")
            return None


def generate_highchart_config(chart_type: str, x_axis_column: str, y_axis_column: str,
                             x_axis_label: str, y_axis_label: str, chart_title: str,
                             json_data: str, z_axis_column: Optional[str] = None,
                             z_axis_label: Optional[str] = None) -> Dict:
    """
    Generate Highcharts configuration from chart parameters.

    Args:
        chart_type: Type of chart (line, column, bar, pie, etc.)
        x_axis_column: Column name for x-axis
        y_axis_column: Column name for y-axis
        x_axis_label: Label for x-axis
        y_axis_label: Label for y-axis
        chart_title: Title for the chart
        json_data: JSON string containing the data
        z_axis_column: Optional column for grouping/series
        z_axis_label: Optional label for z-axis

    Returns:
        Highcharts configuration dictionary
    """
    try:
        logger.info(f"🔧 Generating {chart_type} chart: {chart_title}")

        # Parse the JSON data
        data = json.loads(json_data) if isinstance(json_data, str) else json_data

        # Extract chart data from Elasticsearch results or direct data
        chart_data = []
        if isinstance(data, dict) and 'hits' in data and 'hits' in data['hits']:
            chart_data = [hit['_source'] for hit in data['hits']['hits'] if '_source' in hit]
        elif isinstance(data, list):
            chart_data = data
        else:
            logger.warning(f"Unexpected data format: {type(data)}")
            return _get_empty_chart_config(chart_title)

        if not chart_data:
            logger.warning("No chart data available")
            return _get_empty_chart_config(chart_title)

        # Auto-detect columns if not present in data
        if not any(x_axis_column in item for item in chart_data):
            x_axis_column, y_axis_column = auto_detect_columns(chart_data)
            logger.info(f"Auto-detected columns: x={x_axis_column}, y={y_axis_column}")

        # Extract categories and values
        categories = []
        values = []

        for item in chart_data:
            if x_axis_column in item and y_axis_column in item:
                categories.append(str(item[x_axis_column]))
                try:
                    value = float(item[y_axis_column]) if item[y_axis_column] is not None else 0
                except (ValueError, TypeError):
                    value = 0
                values.append(value)

        # Limit to top 10 items for readability
        if len(categories) > 10:
            combined = list(zip(categories, values))
            combined.sort(key=lambda x: x[1], reverse=True)
            categories = [x[0] for x in combined[:10]]
            values = [x[1] for x in combined[:10]]

        # Generate chart configuration based on type
        if chart_type.lower() == 'pie':
            config = {
                "chart": {"type": "pie", "height": 400},
                "title": {"text": chart_title},
                "series": [{
                    "name": y_axis_label,
                    "data": [{"name": cat, "y": val} for cat, val in zip(categories, values)]
                }],
                "plotOptions": {
                    "pie": {
                        "allowPointSelect": True,
                        "cursor": "pointer",
                        "dataLabels": {"enabled": True},
                        "showInLegend": True
                    }
                }
            }
        else:
            config = {
                "chart": {"type": chart_type.lower(), "height": 400},
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
                    "data": values
                }],
                "plotOptions": {
                    chart_type.lower(): {
                        "dataLabels": {"enabled": len(values) <= 10}
                    }
                }
            }

        logger.info(f"✅ Generated chart config with {len(categories)} data points")
        return config

    except Exception as e:
        logger.error(f"❌ Error generating chart config: {e}")
        return _get_empty_chart_config(chart_title)


def _get_empty_chart_config(title: str) -> Dict:
    """Return a basic empty chart configuration."""
    return {
        "chart": {"type": "column", "height": 400},
        "title": {"text": title},
        "xAxis": {"categories": []},
        "yAxis": {"title": {"text": "Values"}},
        "series": [{"name": "No Data", "data": []}]
    }
