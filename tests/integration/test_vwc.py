# tests/test_wc.py
import os
import pytest
import subprocess
from pathlib import Path
import docker
import shutil
import tempfile

# Define test platforms
PLATFORMS = {"gnu": "ubuntu:latest", "busybox": "alpine:latest", "bsd": "madworx/netbsd:latest"}


# Test case discovery
def get_test_scripts():
    """Get all test scripts from the test_scripts directory"""
    test_dir = Path(__file__).parent / "test_scripts"
    return [f for f in test_dir.glob("*.sh")]


# Container management
@pytest.fixture(scope="module")
def container_factory():
    """Create and manage containers"""
    client = docker.from_env()
    containers = {}

    def get_container(platform):
        if platform not in containers:
            containers[platform] = client.containers.run(PLATFORMS[platform], command="sleep infinity", detach=True)
            # Setup working directory
            containers[platform].exec_run("mkdir -p /tmp/test")
        return containers[platform]

    yield get_container

    # Cleanup
    for platform, container in containers.items():
        container.stop()
        container.remove()


# Run with our implementation
def run_local(script_path):
    """Run test locally with our vwc implementation"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Copy script to temp dir
        temp_script = Path(temp_dir) / script_path.name
        shutil.copy2(script_path, temp_script)
        os.chmod(temp_script, 0o755)

        # Replace wc with vwc in the script
        script_content = temp_script.read_text()
        vwc_cmd = shutil.which("vwc") or "python -m vwc.main"
        modified_content = script_content.replace("wc ", f"{vwc_cmd} ")
        temp_script.write_text(modified_content)

        # Run the script
        result = subprocess.run(f"bash {temp_script}", shell=True, capture_output=True, cwd=temp_dir)

        return {
            "stdout": result.stdout.decode("utf-8"),
            "stderr": result.stderr.decode("utf-8"),
            "exit_code": result.returncode,
        }


# Run in container
def run_in_container(container, script_path):
    """Run test in container with reference implementation"""
    # Copy script to container
    script_content = script_path.read_text()
    temp_script = f"/tmp/test/{script_path.name}"

    container.exec_run(f"bash -c 'cat > {temp_script}'", stdin=script_content.encode())
    container.exec_run(f"chmod +x {temp_script}")

    # Run the script
    exit_code, output = container.exec_run(f"bash {temp_script}", demux=True)

    return {
        "stdout": output[0].decode("utf-8") if output[0] else "",
        "stderr": output[1].decode("utf-8") if output[1] else "",
        "exit_code": exit_code,
    }


# Compare results
def compare_results(vwc_result, ref_result):
    """Compare vwc and reference results"""
    differences = []

    # Compare stdout
    if vwc_result["stdout"] != ref_result["stdout"]:
        differences.append(("stdout", vwc_result["stdout"], ref_result["stdout"]))

    # Compare stderr
    if vwc_result["stderr"] != ref_result["stderr"]:
        differences.append(("stderr", vwc_result["stderr"], ref_result["stderr"]))

    # Compare exit code
    if vwc_result["exit_code"] != ref_result["exit_code"]:
        differences.append(("exit_code", vwc_result["exit_code"], ref_result["exit_code"]))

    return differences


# Dynamically generate test functions
def pytest_generate_tests(metafunc):
    """Generate test functions for each test script and platform"""
    if "test_script" in metafunc.fixturenames and "platform" in metafunc.fixturenames:
        test_scripts = get_test_scripts()
        platforms = list(PLATFORMS.keys())

        # Skip slow platforms if TEST_FAST is set
        if os.environ.get("TEST_FAST"):
            platforms = [p for p in platforms if p != "bsd"]

        metafunc.parametrize("test_script", test_scripts, ids=[t.stem for t in test_scripts])
        metafunc.parametrize("platform", platforms)


# The actual test function
def test_vwc_against_platform(test_script, platform, container_factory):
    """Test vwc against reference platform"""
    # Skip tests if needed
    if platform == "bsd" and os.environ.get("TEST_FAST"):
        pytest.skip("Skipping slow BSD tests")

    # Get container
    container = container_factory(platform)

    # Run with vwc
    vwc_result = run_local(test_script)

    # Run with reference
    ref_result = run_in_container(container, test_script)

    # Compare results
    differences = compare_results(vwc_result, ref_result)

    # Report differences
    for diff_type, vwc_output, ref_output in differences:
        print(f"\n{diff_type} mismatch for {test_script.stem} on {platform}:")
        print(f"vwc output: {repr(vwc_output)}")
        print(f"{platform} output: {repr(ref_output)}")

    # Fail if differences found
    assert not differences, f"Output mismatch for {test_script.stem} on {platform}"
