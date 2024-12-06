import time
from pytest_bdd import given, when, then, scenarios
from src.utils.logging_util import get_logger
from src.utils.config_util import load_config

logger = get_logger(__name__)
# Load configuration once at module level
CONFIG = load_config()
# Link the Gherkin feature file
scenarios("../features/scale_deployment_node_tracking.feature")


@given("a Kubernetes cluster is running")
def verify_cluster_running(k8s_client):
    """Verify that the Kubernetes cluster is accessible."""
    logger.info("Verifying Kubernetes cluster is running...")
    assert k8s_client is not None, "Kubernetes client could not be initialized."
    logger.info("Kubernetes cluster verification successful.")


@given('a deployment named "scale-test" exists in the "scale-test" namespace')
def verify_deployment_exists(k8s_client):
    """Ensure the deployment exists."""
    namespace = CONFIG["k8s"]["namespace"]
    deployment_name = CONFIG["k8s"]["deployment_name"]

    # Retrieve AppsV1Api client
    apps_api = k8s_client("AppsV1Api")
    logger.info(f"Checking if deployment '{deployment_name}' exists in namespace '{namespace}'...")
    response = apps_api.read_namespaced_deployment(name=deployment_name, namespace=namespace)
    assert response is not None, f"Deployment '{deployment_name}' does not exist in namespace '{namespace}'."
    logger.info(f"Deployment '{deployment_name}' exists.")


@when('I scale "scale-test" to 1000 replicas')
def scale_deployment(k8s_client):
    """Scale the deployment to 1000 replicas."""
    namespace = CONFIG["k8s"]["namespace"]
    deployment_name = CONFIG["k8s"]["deployment_name"]
    replicas = 1000

    # Retrieve AppsV1Api client
    apps_api = k8s_client("AppsV1Api")
    logger.info(f"Scaling deployment '{deployment_name}' in namespace '{namespace}' to {replicas} replicas.")
    body = {"spec": {"replicas": replicas}}
    apps_api.patch_namespaced_deployment_scale(name=deployment_name, namespace=namespace, body=body)


@then("new nodes should become ready within 240 seconds")
def verify_nodes_ready(k8s_client):
    """Measure the time taken for nodes to become ready."""
    # Retrieve CoreV1Api client
    core_api = k8s_client("CoreV1Api")
    node_ready_start_time = time.time()
    timeout = 240  # seconds
    interval = 10  # seconds
    all_nodes_ready = False

    logger.info("Waiting for new nodes to become ready...")
    while not all_nodes_ready and (time.time() - node_ready_start_time) < timeout:
        nodes = core_api.list_node().items
        all_nodes_ready = all(
            any(condition.type == "Ready" and condition.status == "True" for condition in node.status.conditions)
            for node in nodes
        )
        if all_nodes_ready:
            break
        time.sleep(interval)

    total_node_ready_time = time.time() - node_ready_start_time
    assert all_nodes_ready, "New nodes did not become ready within the timeout."
    logger.info(f"All nodes became ready in {total_node_ready_time:.2f} seconds.")


@then("all replicas of the deployment should be running and available within 240 seconds")
def verify_pods_ready(k8s_client):
    """Measure the time taken for all replicas to be scheduled and available."""
    namespace = CONFIG["k8s"]["namespace"]
    deployment_name = CONFIG["k8s"]["deployment_name"]

    # Retrieve AppsV1Api client
    apps_api = k8s_client("AppsV1Api")
    pod_schedule_start_time = time.time()
    timeout = 240  # seconds
    interval = 10  # seconds
    pods_ready = False

    logger.info(f"Waiting for deployment '{deployment_name}' to have all replicas running and available...")
    while not pods_ready and (time.time() - pod_schedule_start_time) < timeout:
        response = apps_api.read_namespaced_deployment(name=deployment_name, namespace=namespace)
        pods_ready = (
            response.status.replicas == 1000
            and response.status.available_replicas == 1000
        )
        if pods_ready:
            break
        time.sleep(interval)

    total_pod_ready_time = time.time() - pod_schedule_start_time
    assert pods_ready, f"Deployment '{deployment_name}' did not scale to 1000 replicas within {timeout} seconds."
    logger.info(f"All pods became ready in {total_pod_ready_time:.2f} seconds.")


@then("I log the timing metrics for node and pod readiness")
def log_timing(k8s_client):
    """Log timing metrics for nodes and pods."""
    logger.info("Timing metrics have been logged for both nodes and pods readiness.")