"""Chart generation implementation using DSPy."""
import asyncio
import json
import logging
from typing import Dict, Optional, Tuple, List, Any

import dspy

from core.exceptions import ChartGenerationError
from core.interfaces import IChartGenerator
from modules.signatures import ChartAxisSelector
from util.chart_utils import generate_chart_from_config
from util.performance import monitor_performance

logger = logging.getLogger(__name__)


class DSPyChartGenerator(IChartGenerator):
    """DSPy-based chart generator implementation."""

    def __init__(self, default_chart_type: str = "column"):
        """Initialize the chart generator with DSPy components."""
        self.chart_selector = dspy.ChainOfThought(ChartAxisSelector)
        self.default_chart_type = default_chart_type

    @monitor_performance("chart_generation")
    def generate_chart(self, data: Dict, user_query: str, conversation_history: Optional[List[Dict]] = None) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Generate chart configuration and HTML.

        Args:
            data: Parsed JSON data from query results
            user_query: The user's query string
            conversation_history: Optional conversation history for context

        Returns:
            Tuple of (chart_config, chart_html) or (None, None) if generation fails

        Raises:
            ChartGenerationError: If chart generation fails
        """
        try:
            logger.info(f"Generating chart for query: {user_query}")

            # Extract actual data from the hits
            chart_data = self._extract_chart_data(data)

            if not chart_data:
                logger.warning("No data available for chart generation")
                return None, None

            # Use DSPy to determine best chart configuration
            result = self.chart_selector(
                json_data=json.dumps(chart_data),
                user_query=user_query,
                conversation_history=conversation_history
            )

            # Build the actual chart config with real data
            chart_config = self._build_chart_config(chart_data, result, user_query)

            # Generate HTML for rendering
            chart_html = generate_chart_from_config(chart_config)
            logger.info("Chart generated successfully")

            return chart_config, chart_html

        except Exception as e:
            logger.error(f"Error generating chart: {e}", exc_info=True)
            raise ChartGenerationError(f"Failed to generate chart: {e}") from e

    def _extract_chart_data(self, data: Dict) -> List[Dict[str, Any]]:
        """Extract chart data from Elasticsearch results."""
        try:
            logger.info(f"Extracting chart data from: {type(data)}")
            logger.debug(f"Data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")

            if 'hits' in data and 'hits' in data['hits']:
                # Extract _source data from Elasticsearch hits
                chart_data = [hit['_source'] for hit in data['hits']['hits'] if '_source' in hit]
                logger.info(f"Extracted {len(chart_data)} items from Elasticsearch hits")
                if chart_data:
                    logger.debug(f"Sample data keys: {list(chart_data[0].keys())}")
                return chart_data
            elif isinstance(data, list):
                # Data is already a list of records
                logger.info(f"Data is already a list with {len(data)} items")
                return data
            else:
                logger.warning(f"Unexpected data format for chart: {type(data)}")
                logger.debug(f"Data content: {str(data)[:500]}...")
                return []
        except Exception as e:
            logger.error(f"Error extracting chart data: {e}")
            return []

    def _build_chart_config(self, chart_data: List[Dict], dspy_result: Any, user_query: str) -> Dict:
        """Build the actual chart configuration with real data."""
        try:
            logger.info(f"Building chart config for {len(chart_data)} data items")

            # Get column suggestions from DSPy with better fallbacks
            x_column = getattr(dspy_result, 'x_axis_column', None)
            y_column = getattr(dspy_result, 'y_axis_column', None)
            chart_title = getattr(dspy_result, 'chart_title', f'Data Visualization for: {user_query}')

            # If DSPy didn't provide good columns, analyze the data to find suitable ones
            if not x_column or not y_column or not any(x_column in item for item in chart_data):
                logger.info("DSPy column suggestions not usable, auto-detecting columns")
                x_column, y_column = self._auto_detect_columns(chart_data)

            logger.info(f"Using columns - X: {x_column}, Y: {y_column}")

            x_label = getattr(dspy_result, 'x_axis_label', x_column.replace('_', ' ').title() if x_column else 'Category')
            y_label = getattr(dspy_result, 'y_axis_label', y_column.replace('_', ' ').title() if y_column else 'Value')

            # Extract actual data values
            categories = []
            series_data = []

            for item in chart_data:
                if x_column in item and y_column in item:
                    x_value = str(item[x_column])
                    y_value = item[y_column]

                    # Convert y_value to number if possible
                    try:
                        y_value = float(y_value) if y_value is not None else 0
                    except (ValueError, TypeError):
                        y_value = 0

                    categories.append(x_value)
                    series_data.append(y_value)

            logger.info(f"Extracted {len(categories)} chart data points")

            # Limit to top 10 items for readability
            if len(categories) > 10:
                # Sort by y_value descending and take top 10
                combined = list(zip(categories, series_data))
                combined.sort(key=lambda x: x[1], reverse=True)
                categories = [x[0] for x in combined[:10]]
                series_data = [x[1] for x in combined[:10]]
                logger.info("Limited to top 10 items")

            chart_config = {
                'chart': {'type': self.default_chart_type},
                'title': {'text': chart_title},
                'xAxis': {
                    'categories': categories,
                    'title': {'text': x_label}
                },
                'yAxis': {
                    'title': {'text': y_label}
                },
                'series': [{
                    'name': y_label,
                    'data': series_data
                }],
                'plotOptions': {
                    'column': {
                        'dataLabels': {
                            'enabled': True
                        }
                    }
                }
            }

            logger.info(f"Built chart config with {len(categories)} categories and {len(series_data)} data points")
            return chart_config

        except Exception as e:
            logger.error(f"Error building chart config: {e}", exc_info=True)
            # Return a basic chart structure
            return {
                'chart': {'type': self.default_chart_type},
                'title': {'text': f'Data for: {user_query}'},
                'xAxis': {'categories': []},
                'yAxis': {'title': {'text': 'Values'}},
                'series': [{'name': 'Data', 'data': []}]
            }

    def _auto_detect_columns(self, chart_data: List[Dict]) -> Tuple[str, str]:
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
                # Check if it's numeric
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
        y_column = y_column or (available_keys[1] if len(available_keys) > 1 else available_keys[0]) if available_keys else 'value'

        logger.info(f"Auto-detected columns: X={x_column}, Y={y_column} from available: {available_keys}")
        return x_column, y_column

    @monitor_performance("chart_generation_async")
    async def generate_chart_async(self, data: Dict, user_query: str, conversation_history: Optional[List[Dict]] = None) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Asynchronously generate chart configuration and HTML.

        Args:
            data: Parsed JSON data from query results
            user_query: The user's query string
            conversation_history: Optional conversation history for context

        Returns:
            Tuple of (chart_config, chart_html) or (None, None) if generation fails

        Raises:
            ChartGenerationError: If chart generation fails
        """
        try:
            logger.info(f"Generating chart asynchronously for query: {user_query}")

            # Use asyncio.to_thread for CPU-bound operations
            return await asyncio.to_thread(self.generate_chart, data, user_query, conversation_history)

        except Exception as e:
            logger.error(f"Error generating chart asynchronously: {e}", exc_info=True)
            raise ChartGenerationError(f"Failed to generate chart asynchronously: {e}") from e
