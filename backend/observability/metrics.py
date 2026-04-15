from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

API_REQUEST_COUNT = Counter(
    "syncbank_api_requests_total",
    "Total API requests",
    ["method", "path", "status"],
)

API_REQUEST_DURATION_SECONDS = Histogram(
    "syncbank_api_request_duration_seconds",
    "API request latency in seconds",
    ["method", "path"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

API_IN_PROGRESS = Gauge(
    "syncbank_api_requests_in_progress",
    "Current number of API requests in progress",
)

JOB_TRANSITIONS = Counter(
    "syncbank_job_transitions_total",
    "Total job status transitions",
    ["job_type", "status"],
)

JOB_EXECUTION_DURATION_SECONDS = Histogram(
    "syncbank_job_execution_duration_seconds",
    "Job execution latency in seconds",
    ["job_type", "status"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0),
)

WORKER_IN_PROGRESS = Gauge(
    "syncbank_worker_jobs_in_progress",
    "Current number of worker jobs in progress",
    ["job_type"],
)
