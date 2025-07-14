import pytest
from pytest_bdd import scenarios, given, when, then
from kubernetes import client, config, stream
import tomli  # Or use tomllib in Python 3.11+

scenarios('dns_connectivity.feature')

CONFIG_PATH = "config.toml"
NAMESPACE = "platform-scale-test"
DEPLOYMENT_NAME = "scale-test"

@pytest.fixture(scope="module")
def k8s_api():
    config.load_kube_config()
    return client.CoreV1Api()

@pytest.fixture(scope="module")
def target_ip():
    with open(CONFIG_PATH, "rb") as f:
        config_data = tomli.load(f)
    return config_data["dns"]["target_ip"]

@given('a running deployment named "scale-test" in namespace "platform-scale-test"')
def ensure_deployment_exists():
    pass  # You can validate via AppsV1Api if needed

@given("at least one pod from the deployment is running")
def get_running_pod(k8s_api):
    pods = k8s_api.list_namespaced_pod(
        namespace=NAMESPACE, label_selector="app=scale-test"
    )
    for pod in pods.items:
        if pod.status.phase == "Running":
            return pod.metadata.name
    pytest.fail("No running pod found in deployment")

@when("I ping the configured DNS IP from that pod")
def run_ping(k8s_api, get_running_pod, target_ip):
    command = ["ping", "-c", "3", target_ip]
    try:
        response = stream.stream(
            k8s_api.connect_get_namespaced_pod_exec,
            name=get_running_pod,
            namespace=NAMESPACE,
            command=command,
            stderr=True, stdin=False, stdout=True, tty=False,
        )
        return response
    except Exception as e:
        pytest.fail(f"Ping failed: {e}")

@then("the ping should succeed with 0% packet loss")
def verify_ping_success(run_ping):
    assert "0% packet loss" in run_ping, "Ping failed — connectivity issue"
