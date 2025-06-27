"""Performance monitoring and metrics utilities."""
import functools
import logging
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, Any, Callable, Optional, List


@dataclass
class PerformanceMetrics:
    """Performance metrics data structure."""
    operation_name: str
    start_time: float
    end_time: float
    duration: float
    success: bool
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class PerformanceMonitor:
    """Thread-safe performance monitoring utility."""

    def __init__(self):
        self._metrics: List[PerformanceMetrics] = []
        self._lock = threading.Lock()
        self._operation_counts = defaultdict(int)
        self._operation_durations = defaultdict(list)
        self.logger = logging.getLogger(__name__)

    @contextmanager
    def monitor_operation(self, operation_name: str, **metadata):
        """Context manager for monitoring operation performance."""
        start_time = time.time()
        success = True
        error_message = None

        try:
            yield
        except Exception as e:
            success = False
            error_message = str(e)
            raise
        finally:
            end_time = time.time()
            duration = end_time - start_time

            metrics = PerformanceMetrics(
                operation_name=operation_name,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                success=success,
                error_message=error_message,
                metadata=metadata
            )

            self._record_metrics(metrics)

    def _record_metrics(self, metrics: PerformanceMetrics):
        """Record performance metrics thread-safely."""
        with self._lock:
            self._metrics.append(metrics)
            self._operation_counts[metrics.operation_name] += 1
            self._operation_durations[metrics.operation_name].append(metrics.duration)

            # Log slow operations
            if metrics.duration > 5.0:  # 5 seconds threshold
                self.logger.warning(
                    f"Slow operation detected: {metrics.operation_name} "
                    f"took {metrics.duration:.2f}s"
                )

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of performance metrics."""
        with self._lock:
            summary = {}

            for operation_name in self._operation_counts:
                durations = self._operation_durations[operation_name]

                summary[operation_name] = {
                    'count': self._operation_counts[operation_name],
                    'avg_duration': sum(durations) / len(durations) if durations else 0,
                    'min_duration': min(durations) if durations else 0,
                    'max_duration': max(durations) if durations else 0,
                    'total_duration': sum(durations)
                }

            return summary

    def get_recent_metrics(self, limit: int = 100) -> List[PerformanceMetrics]:
        """Get recent performance metrics."""
        with self._lock:
            return self._metrics[-limit:] if self._metrics else []

    def clear_metrics(self):
        """Clear all recorded metrics."""
        with self._lock:
            self._metrics.clear()
            self._operation_counts.clear()
            self._operation_durations.clear()


# Global performance monitor instance
performance_monitor = PerformanceMonitor()


def monitor_performance(operation_name: Optional[str] = None, **metadata):
    """Decorator for monitoring function performance."""
    def decorator(func: Callable) -> Callable:
        op_name = operation_name or f"{func.__module__}.{func.__name__}"

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with performance_monitor.monitor_operation(op_name, **metadata):
                return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            with performance_monitor.monitor_operation(op_name, **metadata):
                return await func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        if hasattr(func, '__call__'):
            import asyncio
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return wrapper

        return wrapper

    return decorator


def get_performance_summary() -> Dict[str, Any]:
    """Get global performance summary."""
    return performance_monitor.get_metrics_summary()


def clear_performance_metrics():
    """Clear global performance metrics."""
    performance_monitor.clear_metrics()
