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
    duration = test_results["end_time"] - test_results["start_time"]

    # Collect log lines
    lines = []
    lines.append("📄 Pytest Execution Summary")
    lines.append(f"🕒 Duration: {duration.total_seconds():.2f} seconds")
    lines.append(f"✅ Passed: {len(test_results['passed'])}")
    lines.append(f"❌ Failed: {len(test_results['failed'])}")
    lines.append(f"⚠️ Skipped: {len(test_results['skipped'])}")
    lines.append(f"📦 Total: {test_results['total']}")

    if test_results["passed"]:
        lines.append("\n✅ Passed Tests:")
        lines.extend([f"  - {t}" for t in test_results["passed"]])
    if test_results["failed"]:
        lines.append("\n❌ Failed Tests:")
        lines.extend([f"  - {t}" for t in test_results["failed"]])
    if test_results["skipped"]:
        lines.append("\n⚠️ Skipped Tests:")
        lines.extend([f"  - {t}" for t in test_results["skipped"]])

    # DNS Telemetry Summary
    if dns_metrics_global:
        lines.append("\n🌐 DNS Resolution Summary")
        for m in dns_metrics_global:
            lines.append(
                f"  {m.get('host', '-')}: {m.get('ip_address', '-')} "
                f"via {m.get('nameserver', '-')} in {m.get('duration_ms', '-')} ms"
            )

    # Join into single string for structured log
    summary_log = "\n".join(lines)
    logger.bind(summary_type="pytest-summary", component="test-telemetry").info(summary_log)

    # Also print rich table locally (optional)
    if dns_metrics_global:
        table = Table(title="DNS Resolution Telemetry", show_lines=True, expand=True)
        table.add_column("Host", style="cyan", no_wrap=False)
        table.add_column("IP Address", style="green", min_width=15, overflow="fold")
        table.add_column("Resolver", style="magenta", min_width=15, overflow="fold")
        table.add_column("Time (ms)", justify="right", min_width=10)
        table.add_column("Success", justify="center", min_width=7)
        table.add_column("Error", style="red", overflow="fold", min_width=60)

        for m in dns_metrics_global:
            table.add_row(
                m.get("host", "-"),
                m.get("ip_address", "-"),
                m.get("nameserver", "-"),
                f"{m.get('duration_ms', '-')}",
                "[green]✅[/green]" if m.get("success") else "[red]❌[/red]",
                m.get("error", "") or "-"
            )
        console.print(table)
