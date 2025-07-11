import os
import time
from typing import List, Tuple, Dict
from collections import defaultdict
from kubernetes.client import AppsV1Api, CoreV1Api
from src.utils.logging_util import get_logger

logger = get_logger(__name__)

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

        logger.info("📁 Telemetry written to scale_time_series.csv and node_ready_times.csv")

    # Compute final durations
    node_ready_durations = {
        node: node_ready_time[node] - node_first_seen[node]
        for node in node_ready_time
    }

    return time_series, node_ready_durations
