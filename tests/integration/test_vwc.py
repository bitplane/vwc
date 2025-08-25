# Note to LLMs:
#   Don't mess with this file unless explicitly asked to change it, and if you do,
#   do it very carefully. We spent too much time arguing about it.
import os
import shutil
import subprocess
from pathlib import Path

import pytest


# Get test scripts
def get_test_scripts():
    """Get all test scripts from the test_scripts directory"""
    test_dir = Path(__file__).parent / "test_scripts"
    return [f for f in test_dir.glob("*.sh")]


# Get available platforms based on Containerfiles
def get_platforms():
    """Get all platforms based on available Containerfiles"""
    containerfile_dir = Path(__file__).parent / "containerfiles"
    return [f.name.split(".", 1)[1] for f in containerfile_dir.glob("Containerfile.*")]


# Prepare build directory
def prepare_build_dir():
    """Prepare build directory by copying required files"""
    script_path = Path(__file__).parent / "build.sh"

    # Make sure build script is executable
    os.chmod(script_path, 0o755)

    # Run the build script
    subprocess.run([str(script_path)], check=True)


# Build Podman image for a platform - only once per session
@pytest.fixture(scope="session")
def podman_image_factory(request):
    """Build Podman images for platforms (only once per session)"""
    # Prepare build directory
    prepare_build_dir()

    built_images = {}

    def _get_image(platform):
        if platform in built_images:
            return built_images[platform]

        # Use the build directory as context
        build_dir = Path(__file__).parent / "build"
        containerfile_path = Path(__file__).parent / "containerfiles" / f"Containerfile.{platform}"

        # Build the image
        image_name = f"vwc-test-{platform}"

        result = subprocess.run(
            ["podman", "build", "-t", image_name, "-f", str(containerfile_path), str(build_dir)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Podman build failed: {result.stderr}")

        built_images[platform] = image_name
        return image_name

    # Cleanup after tests
    def _cleanup():
        for image_name in built_images.values():
            try:
                subprocess.run(["podman", "rmi", image_name], check=False)
            except Exception:
                pass

    request.addfinalizer(_cleanup)
    return _get_image


def empty_dir(path: Path):
    """Remove all files and directories in the given path, then recreate it"""
    if path.exists():
        for child in path.iterdir():
            if child.is_file() or child.is_symlink():
                child.unlink()
            elif child.is_dir():
                shutil.rmtree(child)
    else:
        path.mkdir(parents=True)


# Run a test with either original wc or vwc
def run_test(image_name, script_path, use_vwc=False):
    """Run a test script in the container with either original wc or vwc"""
    output_dir = Path(f"/tmp/vwc-test-{os.getpid()}/{script_path.stem}/{use_vwc}")
    # remove and recreate the output dir
    empty_dir(output_dir)

    # Get project source
    project_root = Path(__file__).parent.parent.parent

    # Use the run_test.sh script
    runner_script = Path(__file__).parent / "run_test.sh"

    # Run the container
    subprocess.run(
        [
            "podman",
            "run",
            "--rm",
            # Mount the source directory
            "-v",
            f"{project_root}:/app:ro",
            # Mount test script and runner
            "-v",
            f"{script_path.absolute()}:/test_script.sh:ro",
            "-v",
            f"{runner_script.absolute()}:/run_test.sh:ro",
            # Mount output directory
            "-v",
            f"{output_dir}:/output",
            image_name,
            "/run_test.sh",
            "/test_script.sh",
            "/output",
            "vwc" if use_vwc else "wc",
        ],
        check=True,
        capture_output=True,
    )

    return output_dir


def assert_identical(wc_dir, vwc_dir):
    """Compare all files in the output directories"""

    # Get all files in both directories
    all_files = set()
    for file_path in wc_dir.glob("*"):
        all_files.add(file_path.name)
    for file_path in vwc_dir.glob("*"):
        all_files.add(file_path.name)

    all_files = sorted(all_files)

    if not all_files:
        raise ValueError("No files found in either output directory")

    # Compare each file
    for filename in all_files:
        expected_file = wc_dir / filename
        actual_file = vwc_dir / filename

        assert expected_file.exists(), f"Unexpected file: {filename}"
        assert actual_file.exists(), f"Missing expected file: {filename}"

        # skip directories, but only if they're in both
        if expected_file.is_dir() and actual_file.is_dir():
            continue

        # Compare file contents
        with open(expected_file, "rb") as f:
            expected = f.read()
        with open(actual_file, "rb") as f:
            actual = f.read()

        print(f"Comparing {filename}:\n")
        print(f"Expected: {expected}")
        print(f"Actual:   {actual}\n\n")

        assert actual == expected, f"Differences in {filename}"


# Generate test parameters
def pytest_generate_tests(metafunc):
    """Generate test functions for each test script and platform"""
    if "script" in metafunc.fixturenames and "platform" in metafunc.fixturenames:
        scripts = get_test_scripts()
        platforms = get_platforms()

        metafunc.parametrize("script", scripts, ids=[s.stem for s in scripts])
        metafunc.parametrize("platform", platforms)


# Test function
def test_vwc_integration(script, platform, podman_image_factory):
    """Test that vwc behaves identically to the platform's native wc"""
    # Get the Podman image for this platform
    image_name = podman_image_factory(platform)

    # Run with original wc
    wc_output_dir = run_test(image_name, script, use_vwc=False)

    # Run with vwc
    vwc_output_dir = run_test(image_name, script, use_vwc=True)

    print("script contents:")
    print(script.read_text())

    # Compare all output files
    assert_identical(wc_output_dir, vwc_output_dir)
