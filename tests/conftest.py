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


def pytest_sessionfinish(session, exitstatus):
    test_results["end_time"] = datetime.utcnow()
    duration = test_results["end_time"] - test_results["start_time"]

    # Summary counts
    passed = len(test_results["passed"])
    failed = len(test_results["failed"])
    skipped = len(test_results["skipped"])
    total = test_results["total"]

    # Print overall result summary
    logger = logging.getLogger("pytest-summary")
    logger.info(f"\n🧪 Pytest Execution Summary")
    logger.info(f"⏱️ Duration: {duration.total_seconds():.2f} seconds")
    logger.info(f"✅ Passed: {passed}")
    logger.info(f"❌ Failed: {failed}")
    logger.info(f"⚠️ Skipped: {skipped}")
    logger.info(f"📦 Total: {total}\n")

    # Print test names by category
    if test_results["passed"]:
        logger.info("✅ Passed Tests:")
        for t in test_results["passed"]:
            logger.info(f"  • {t}")
    if test_results["failed"]:
        logger.error("❌ Failed Tests:")
        for t in test_results["failed"]:
            logger.error(f"  • {t}")
    if test_results["skipped"]:
        logger.warning("⚠️ Skipped Tests:")
        for t in test_results["skipped"]:
            logger.warning(f"  • {t}")

    # DNS Resolution Summary as Rich table (if available)
    if dns_metrics_global:
        table = Table(title="DNS Resolution Telemetry", show_lines=True, expand=True)
        table.add_column("Host", style="cyan", no_wrap=False)
        table.add_column("IP Address", style="green", min_width=15, overflow="fold")
        table.add_column("Resolver", style="magenta", min_width=15, overflow="fold")
        table.add_column("Time (ms)", justify="right", min_width=10)
        table.add_column("Success", justify="center", min_width=7)
        table.add_column("Error", style="red", overflow="fold", min_width=60)

        for m in dns_metrics_global:
            status_icon = "[green]✅[/green]" if m.get("success") else "[red]❌[/red]"
            table.add_row(
                m.get("host", "-"),
                m.get("ip_address", "-"),
                m.get("nameserver", "-"),
                f"{m.get('duration_ms', '-')}",
                status_icon,
                m.get("error", "") or ""
            )
        console.print("\n[bold cyan]🧭 DNS Resolution Summary[/bold cyan]")
        console.print(table)

        # Optional plain log for GCP
        dns_plain_log = "\nDNS Resolution Summary:\n"
        for m in dns_metrics_global:
            dns_plain_log += f"{m['host']} → {m.get('ip_address')} in {m.get('duration_ms')} ms via {m.get('nameserver')}\n"
        logger.bind(summary_type="dns-telemetry", component="pytest").info(dns_plain_log)

    # Emit full test_results dict for structured log
    logger.bind(summary_type="pytest-results", component="pytest").info(test_results)
