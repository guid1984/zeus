import pytest
import time
import logging
from src.utils.k8s_client import KubernetesClient
from datetime import datetime

# Configure global logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_protocol(item):
    """
    Hook to log the start, end, and duration of each test.
    """
    logger.info(f"Starting test: {item.name}")
    start_time = time.time()
    yield  # Execute the test
    end_time = time.time()
    duration = end_time - start_time
    logger.info(f"Finished test: {item.name} in {duration:.3f} seconds.")


@pytest.fixture(scope="module")
def k8s_client():
    """
    Fixture to provide Kubernetes API clients dynamically.
    """
    config_file = "config/settings.toml"
    logger.info(f"Initializing Kubernetes client with config file: {config_file}")
    k8s = KubernetesClient(config_file=config_file)

    def get_client(api_type):
        """
        Retrieve the specified Kubernetes API client.

        Args:
            api_type (str): Type of Kubernetes API client (e.g., "AppsV1Api", "CoreV1Api").

        Returns:
            object: The requested Kubernetes API client instance.
        """
        logger.debug(f"Fetching client for API type: {api_type}")
        return k8s.get_client(api_type)

    return get_client

import pytest
import logging
from datetime import datetime

# Track test start time and outcomes
test_results = {
    "start_time": None,
    "end_time": None,
    "passed": [],
    "failed": [],
    "skipped": [],
    "total": 0
}

@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    test_results["start_time"] = datetime.utcnow()

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    result = outcome.get_result()

    if result.when == "call":
        nodeid = item.nodeid
        test_results["total"] += 1

        if result.outcome == "passed":
            test_results["passed"].append(nodeid)
        elif result.outcome == "failed":
            test_results["failed"].append(nodeid)
        elif result.outcome == "skipped":
            test_results["skipped"].append(nodeid)

@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    test_results["end_time"] = datetime.utcnow()
    duration = (test_results["end_time"] - test_results["start_time"]).total_seconds()

    passed = len(test_results["passed"])
    failed = len(test_results["failed"])
    skipped = len(test_results["skipped"])
    total = test_results["total"]

    # Prepare log lines
    lines = []
    lines.append("📋 Pytest Execution Summary")
    lines.append(f"🕒 Duration: {duration:.2f} seconds")
    lines.append(f"✅ Passed: {passed}")
    lines.append(f"❌ Failed: {failed}")
    lines.append(f"⚠️ Skipped: {skipped}")
    lines.append(f"📦 Total: {total}")

    # DNS Resolution summary (text-safe)
    if dns_metrics_global:
        # Print to console using Rich (visual table)
        print_dns_telemetry_rich(dns_metrics_global)

        # Also include simple text log for CI
        lines.append("\n🌐 DNS Resolution Summary:")
        for m in dns_metrics_global:
            host = m.get("host", "-")
            success = "✅" if m.get("success") else "❌"
            duration_ms = m.get("duration_ms", "-")
            nameserver = m.get("nameserver", "-")
            lines.append(f"- {host}: {success} ({duration_ms} ms) via {nameserver}")

    # Combine and print the summary
    summary_log = "\n".join(lines)
    logger.info(summary_log)

    # Optional: send structured log for GCP if needed
    logger.bind(summary_type="pytest-summary", component="test-telemetry").info(summary_log)
