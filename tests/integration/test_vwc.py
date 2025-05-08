# tests/test_wc.py
import os
import subprocess
import tempfile
from pathlib import Path

import docker
import pytest

# Simple platform definitions
PLATFORMS = {"gnu": "ubuntu:latest", "busybox": "alpine:latest", "bsd": "madworx/netbsd:latest"}


# Run a test case against a specific platform
def run_test(test_dir, platform, container):
    """Run a single test against a specified platform container"""
    # Create working directory in container
    container.exec_run("mkdir -p /tmp/test")

    # Run setup if it exists
    setup_file = test_dir / "setup.sh"
    if setup_file.exists():
        setup_script = setup_file.read_text()
        container.exec_run(f"sh -c 'cd /tmp/test && {setup_script}'")

    # Run the test script
    run_script = (test_dir / "run.sh").read_text()
    code, output = container.exec_run(f"sh -c 'cd /tmp/test && {run_script}'")

    # Get expected output - first try platform-specific, then fall back to generic
    expected_file = test_dir / f"output_{platform}.txt"
    if not expected_file.exists():
        expected_file = test_dir / "output.txt"

    expected = expected_file.read_text().strip()
    actual = output.decode("utf-8").strip()

    return expected, actual


# Test our vwc implementation locally
def test_vwc():
    """Test our vwc implementation against reference test cases"""
    test_cases_dir = Path(__file__).parent / "test_cases"

    for test_dir in test_cases_dir.iterdir():
        if not test_dir.is_dir():
            continue

        # Work in a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Copy test files
            os.system(f"cp -r {test_dir}/* {temp_path}/")

            # Run setup if it exists
            setup_file = temp_path / "setup.sh"
            if setup_file.exists():
                subprocess.run(["bash", setup_file], cwd=temp_path, check=True)

            # Run test replacing wc with vwc
            run_script = (temp_path / "run.sh").read_text()
            run_script = run_script.replace("wc", "vwc")

            result = subprocess.run(run_script, shell=True, capture_output=True, text=True, cwd=temp_path)

            # Compare with expected output
            expected = (test_dir / "output.txt").read_text().strip()
            assert (
                result.stdout.strip() == expected
            ), f"Output mismatch for {test_dir.name}:\nExpected: {expected}\nActual: {result.stdout}"


# Container test fixture - avoids creating containers unless they're needed
@pytest.fixture(scope="module")
def containers():
    """Create and yield containers for each platform"""
    client = docker.from_env()
    containers = {}

    # Only create containers if test_container is called
    yield lambda platform: containers.setdefault(
        platform, client.containers.run(PLATFORMS[platform], command="sleep infinity", detach=True, remove=True)
    )

    # Cleanup
    for container in containers.values():
        try:
            container.stop()
        except:  # noqa: E722
            pass


# Test against reference implementations
def test_reference_implementations(containers):
    """Compare our implementation against reference ones in containers"""
    test_cases_dir = Path(__file__).parent / "test_cases"

    for test_dir in test_cases_dir.iterdir():
        if not test_dir.is_dir() or not (test_dir / "run.sh").exists():
            continue

        test_name = test_dir.name
        print(f"\nTesting: {test_name}")

        # Get our implementation's output
        local_result = subprocess.run(
            (test_dir / "run.sh").read_text().replace("wc", "vwc"), shell=True, capture_output=True, text=True
        )
        vwc_output = local_result.stdout.strip()

        # Compare with each reference platform
        for platform in PLATFORMS:
            # Skip BSD if TEST_FAST is set (it's slow to start)
            if platform == "bsd" and os.environ.get("TEST_FAST"):
                continue

            print(f"  Comparing with {platform}...")

            # Create container on first use
            container = containers(platform)

            expected, actual = run_test(test_dir, platform, container)

            # Check if our implementation matches the reference
            if vwc_output != actual:
                print(f"  Output mismatch with {platform}:")
                print(f"  vwc: {vwc_output}")
                print(f"  {platform}: {actual}")
