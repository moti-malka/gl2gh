"""
Prometheus metrics for monitoring and observability.

Provides metrics collection and export in Prometheus format for monitoring
system performance, API usage, and business metrics.
"""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock
from typing import Any


class MetricType:
    """Metric type constants."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class Metric:
    """Base metric class."""
    
    def __init__(self, name: str, help_text: str, metric_type: str, labels: list[str] | None = None):
        self.name = name
        self.help_text = help_text
        self.metric_type = metric_type
        self.labels = labels or []
        self.values: dict[tuple, float] = defaultdict(float)
        self.lock = Lock()
    
    def _make_key(self, labels: dict[str, str] | None = None) -> tuple:
        """Create a key from label values."""
        if not labels:
            return ()
        return tuple(labels.get(label, "") for label in self.labels)
    
    def _format_labels(self, key: tuple) -> str:
        """Format labels for Prometheus output."""
        if not key:
            return ""
        label_pairs = [f'{label}="{value}"' for label, value in zip(self.labels, key)]
        return "{" + ",".join(label_pairs) + "}"
    
    def to_prometheus(self) -> str:
        """Convert metric to Prometheus text format."""
        lines = [
            f"# HELP {self.name} {self.help_text}",
            f"# TYPE {self.name} {self.metric_type}",
        ]
        
        with self.lock:
            for key, value in sorted(self.values.items()):
                labels = self._format_labels(key)
                lines.append(f"{self.name}{labels} {value}")
        
        return "\n".join(lines)


class Counter(Metric):
    """Counter metric - monotonically increasing value."""
    
    def __init__(self, name: str, help_text: str, labels: list[str] | None = None):
        super().__init__(name, help_text, MetricType.COUNTER, labels)
    
    def inc(self, amount: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Increment counter."""
        key = self._make_key(labels)
        with self.lock:
            self.values[key] += amount
    
    def get(self, labels: dict[str, str] | None = None) -> float:
        """Get current counter value."""
        key = self._make_key(labels)
        with self.lock:
            return self.values[key]


class Gauge(Metric):
    """Gauge metric - value that can go up or down."""
    
    def __init__(self, name: str, help_text: str, labels: list[str] | None = None):
        super().__init__(name, help_text, MetricType.GAUGE, labels)
    
    def set(self, value: float, labels: dict[str, str] | None = None) -> None:
        """Set gauge value."""
        key = self._make_key(labels)
        with self.lock:
            self.values[key] = value
    
    def inc(self, amount: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Increment gauge."""
        key = self._make_key(labels)
        with self.lock:
            self.values[key] += amount
    
    def dec(self, amount: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Decrement gauge."""
        key = self._make_key(labels)
        with self.lock:
            self.values[key] -= amount
    
    def get(self, labels: dict[str, str] | None = None) -> float:
        """Get current gauge value."""
        key = self._make_key(labels)
        with self.lock:
            return self.values[key]


class Histogram(Metric):
    """Histogram metric - distribution of values."""
    
    # Default buckets for latency in seconds
    DEFAULT_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
    
    def __init__(
        self,
        name: str,
        help_text: str,
        labels: list[str] | None = None,
        buckets: list[float] | None = None,
    ):
        super().__init__(name, help_text, MetricType.HISTOGRAM, labels)
        self.buckets = sorted(buckets or self.DEFAULT_BUCKETS)
        self.sums: dict[tuple, float] = defaultdict(float)
        self.counts: dict[tuple, int] = defaultdict(int)
        self.bucket_counts: dict[tuple, dict[float, int]] = defaultdict(lambda: defaultdict(int))
    
    def observe(self, value: float, labels: dict[str, str] | None = None) -> None:
        """Observe a value."""
        key = self._make_key(labels)
        with self.lock:
            self.sums[key] += value
            self.counts[key] += 1
            
            # Update bucket counts
            for bucket in self.buckets:
                if value <= bucket:
                    self.bucket_counts[key][bucket] += 1
    
    def to_prometheus(self) -> str:
        """Convert histogram to Prometheus text format."""
        lines = [
            f"# HELP {self.name} {self.help_text}",
            f"# TYPE {self.name} {self.metric_type}",
        ]
        
        with self.lock:
            for key in sorted(self.sums.keys()):
                base_labels = self._format_labels(key)
                
                # Output bucket counts
                cumulative = 0
                for bucket in self.buckets:
                    cumulative += self.bucket_counts[key].get(bucket, 0)
                    bucket_labels = base_labels.rstrip("}") + f',le="{bucket}"' + "}"
                    if not base_labels:
                        bucket_labels = f'{{le="{bucket}"}}'
                    lines.append(f"{self.name}_bucket{bucket_labels} {cumulative}")
                
                # Output +Inf bucket
                inf_labels = base_labels.rstrip("}") + ',le="+Inf"' + "}"
                if not base_labels:
                    inf_labels = '{le="+Inf"}'
                lines.append(f"{self.name}_bucket{inf_labels} {self.counts[key]}")
                
                # Output sum and count
                lines.append(f"{self.name}_sum{base_labels} {self.sums[key]}")
                lines.append(f"{self.name}_count{base_labels} {self.counts[key]}")
        
        return "\n".join(lines)


class MetricsRegistry:
    """Registry for all metrics."""
    
    def __init__(self):
        self.metrics: dict[str, Metric] = {}
        self.lock = Lock()
    
    def register(self, metric: Metric) -> Metric:
        """Register a metric."""
        with self.lock:
            if metric.name in self.metrics:
                raise ValueError(f"Metric {metric.name} already registered")
            self.metrics[metric.name] = metric
        return metric
    
    def get(self, name: str) -> Metric | None:
        """Get a metric by name."""
        with self.lock:
            return self.metrics.get(name)
    
    def to_prometheus(self) -> str:
        """Export all metrics in Prometheus text format."""
        lines = []
        with self.lock:
            for metric in sorted(self.metrics.values(), key=lambda m: m.name):
                lines.append(metric.to_prometheus())
                lines.append("")  # Blank line between metrics
        
        return "\n".join(lines)


# Global registry
_registry = MetricsRegistry()


def get_registry() -> MetricsRegistry:
    """Get the global metrics registry."""
    return _registry


# Application metrics
api_requests_total = _registry.register(
    Counter(
        "gitlab_api_requests_total",
        "Total number of GitLab API requests",
        labels=["method", "endpoint", "status_code"],
    )
)

api_request_duration_seconds = _registry.register(
    Histogram(
        "gitlab_api_request_duration_seconds",
        "GitLab API request duration in seconds",
        labels=["method", "endpoint", "status_code"],
    )
)

api_rate_limit_remaining = _registry.register(
    Gauge(
        "gitlab_api_rate_limit_remaining",
        "Remaining GitLab API rate limit",
        labels=[],
    )
)

discovery_groups_total = _registry.register(
    Counter(
        "discovery_groups_total",
        "Total number of groups discovered",
        labels=["status"],
    )
)

discovery_projects_total = _registry.register(
    Counter(
        "discovery_projects_total",
        "Total number of projects discovered",
        labels=["status", "complexity"],
    )
)

discovery_errors_total = _registry.register(
    Counter(
        "discovery_errors_total",
        "Total number of discovery errors",
        labels=["type", "step"],
    )
)

discovery_duration_seconds = _registry.register(
    Gauge(
        "discovery_duration_seconds",
        "Total discovery duration in seconds",
        labels=[],
    )
)

active_operations = _registry.register(
    Gauge(
        "active_operations",
        "Number of currently active operations",
        labels=["operation_type"],
    )
)


class Timer:
    """Context manager for timing operations."""
    
    def __init__(self, histogram: Histogram, labels: dict[str, str] | None = None):
        self.histogram = histogram
        self.labels = labels
        self.start_time = None
    
    def __enter__(self):
        """Start timing."""
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Record duration."""
        if self.start_time is not None:
            duration = time.time() - self.start_time
            self.histogram.observe(duration, self.labels)


def record_api_request(
    method: str,
    endpoint: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    """Record an API request for metrics."""
    labels = {
        "method": method,
        "endpoint": endpoint,
        "status_code": str(status_code),
    }
    
    api_requests_total.inc(labels=labels)
    api_request_duration_seconds.observe(duration_seconds, labels=labels)


def record_discovery_result(
    entity_type: str,
    status: str,
    complexity: str | None = None,
) -> None:
    """Record a discovery result."""
    if entity_type == "group":
        discovery_groups_total.inc(labels={"status": status})
    elif entity_type == "project":
        labels = {"status": status, "complexity": complexity or "unknown"}
        discovery_projects_total.inc(labels=labels)


def metrics_endpoint() -> str:
    """
    Generate metrics in Prometheus text format.
    
    Returns:
        Metrics in Prometheus exposition format
    """
    return get_registry().to_prometheus()
