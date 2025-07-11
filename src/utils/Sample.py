import os
import time
from typing import List, Tuple, Dict
from collections import defaultdict
from statistics import mean
from kubernetes.client import AppsV1Api, CoreV1Api
from app.src.utils.logging_util import get_logger
from rich.table import Table
from rich.console import Console
import dns.resolver


logger = get_logger(__name__)
console = Console()


def track_scaling_telemetry(
    apps_api: AppsV1Api,
    core_api: CoreV1Api,
    namespace: str,
    deployment_name: str,
    target_replicas: int,
    timeout: int = 600,
    interval: int = 10,
    write_csv: bool = True,
) -> Tuple[List[Tuple[int, int, int, int]], Dict[str, int]]:
    """
    Tracks the scaling progress of a Kubernetes Deployment in terms of pod availability and node readiness.
    
    Returns:
        - time_series: List of (elapsed_time_sec, available_replicas, total_nodes, ready_nodes)
        - node_ready_durations: Dict[node_name] = time_to_ready_sec
    """

    start_time = time.time()
    initial_nodes = {n.metadata.name for n in core_api.list_node().items}
    node_first_seen = dict()
    node_ready_time = dict()
    time_series = []

    logger.info("📊 Starting GKE scaling telemetry...")

    while time.time() - start_time < timeout:
        elapsed = int(time.time() - start_time)

        # Pod availability
        dep_status = apps_api.read_namespaced_deployment(name=deployment_name, namespace=namespace)
        available = dep_status.status.available_replicas or 0

        # Node state
        current_nodes = core_api.list_node().items
        all_nodes = {n.metadata.name for n in current_nodes}
        new_nodes = all_nodes - initial_nodes

        for node in current_nodes:
            name = node.metadata.name
            if name not in node_first_seen:
                node_first_seen[name] = elapsed

            for condition in node.status.conditions:
                if condition.type == "Ready" and condition.status == "True":
                    if name not in node_ready_time:
                        node_ready_time[name] = elapsed

        total_nodes = len(all_nodes)
        ready_nodes = len(node_ready_time)

        logger.info(f"t+{elapsed}s: {available}/{target_replicas} replicas | {total_nodes} nodes | {ready_nodes} ready")

        time_series.append((elapsed, available, total_nodes, ready_nodes))

        if available >= target_replicas:
            logger.info("✅ Deployment scaled successfully.")
            break

        time.sleep(interval)
    else:
        logger.warning(f"⚠️ Timeout reached ({timeout}s); only {available} replicas available.")

    # Final summary data
    final_elapsed = int(time.time() - start_time)
    final_available = time_series[-1][1]
    final_nodes = time_series[-1][2]

    # Compute durations
    node_ready_durations = {
        node: node_ready_time[node] - node_first_seen[node]
        for node in node_ready_time
    }

    new_node_names = set(node_ready_durations.keys()) - initial_nodes
    new_node_count = len(new_node_names)
    if new_node_count:
        durations = [node_ready_durations[n] for n in new_node_names]
        min_t = min(durations)
        max_t = max(durations)
        avg_t = round(mean(durations), 2)
    else:
        min_t = max_t = avg_t = 0

    # 📄 CSV Export
    if write_csv:
        with open("scale_time_series.csv", "w") as f:
            f.write("time_sec,available_replicas,total_nodes,ready_nodes\n")
            for t, a, n, r in time_series:
                f.write(f"{t},{a},{n},{r}\n")

        with open("node_ready_times.csv", "w") as f:
            f.write("node_name,first_seen_sec,ready_at_sec,time_to_ready_sec\n")
            for node in node_ready_time:
                first_seen = node_first_seen[node]
                ready_at = node_ready_time[node]
                time_to_ready = ready_at - first_seen
                f.write(f"{node},{first_seen},{ready_at},{time_to_ready}\n")

    # 🧾 Tabular Summary
    table = Table(title="📈 GKE Scaling Summary", style="bold white")

    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")

    table.add_row("Target Replicas", str(target_replicas))
    table.add_row("Achieved Replicas", str(final_available))
    table.add_row("Total Time (s)", str(final_elapsed))
    table.add_row("Initial Node Count", str(len(initial_nodes)))
    table.add_row("Final Node Count", str(final_nodes))
    table.add_row("New Nodes Added", str(new_node_count))
    table.add_row("Min Node Ready Time (s)", str(min_t))
    table.add_row("Max Node Ready Time (s)", str(max_t))
    table.add_row("Avg Node Ready Time (s)", str(avg_t))

    console.print(table)

    return time_series, node_ready_durations


def track_dns_resolution_telemetry(
    host: str,
    timeout: float = 5.0,
    expect_nodelocal: bool = True
) -> Dict[str, Any]:
    """
    Resolves the given FQDN and captures telemetry on:
    - IP address
    - Resolution time
    - DNS server used
    - Whether NodeLocal DNS was used (169.254.20.10)

    Returns a dict containing all metrics.
    """

    try:
        resolver = dns.resolver.Resolver()
        resolver.lifetime = timeout
        resolver.timeout = timeout

        start = time.time()
        answer = resolver.resolve(host)
        end = time.time()

        ip_address = answer[0].to_text()
        nameserver = resolver.nameservers[0]
        duration_ms = round((end - start) * 1000, 2)

        logger.info(f"✅ Resolved {host} to {ip_address} via {nameserver} in {duration_ms} ms")

        if expect_nodelocal and not nameserver.startswith("169.254"):
            logger.warning(f"⚠️ Resolution for {host} did not use NodeLocal DNS (used: {nameserver})")

        return {
            "host": host,
            "ip": ip_address,
            "nameserver": nameserver,
            "duration_ms": duration_ms,
            "success": True,
            "error": "",
        }

    except Exception as e:
        logger.error(f"❌ DNS resolution failed for {host}: {e}")
        return {
            "host": host,
            "ip": None,
            "nameserver": None,
            "duration_ms": None,
            "success": False,
            "error": str(e),
        }

def format_dns_telemetry_table(metrics: list[dict]) -> str:
    """
    Return a Markdown-style table summarizing DNS resolution telemetry.
    """
    if not metrics:
        return "No DNS telemetry data available."

    header = "| Host | IP Address | Resolver | Time (ms) | Success | Error |\n"
    divider = "|------|------------|----------|-----------|---------|-------|\n"
    rows = []

    for m in metrics:
        rows.append(
            f"| {m['host']} "
            f"| {m.get('ip') or '-'} "
            f"| {m.get('nameserver') or '-'} "
            f"| {m.get('duration_ms') or '-'} "
            f"| {'✅' if m['success'] else '❌'} "
            f"| {m.get('error', '')[:50]} |"
        )

    return header + divider + "\n".join(rows)


