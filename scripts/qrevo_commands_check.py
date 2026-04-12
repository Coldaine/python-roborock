"""Test CLI commands for Qrevo Curv 2 Flow (model a245) with mocked authentication.

This script tests the CLI command flow without requiring real credentials.
"""

import json
import sys
from io import StringIO
from pathlib import Path
from click.testing import CliRunner

# Add the project root to path
sys.path.insert(0, str(Path(__file__).parent))

from roborock.cli import RoborockContext, cli
from roborock.data import UserData
from tests.mock_data import USER_DATA

# Load a245 specific data
A245_PRODUCT_DATA = {
    "id": "64Pgg7cwjxHqT2qQrEh7Ib",
    "name": "Qrevo Curv 2 Flow",
    "model": "roborock.vacuum.a245",
    "category": "robot.vacuum.cleaner",
    "capability": 0,
    "schema": [],
}

A245_DEVICE_DATA = {
    "duid": "device-id-a245",
    "name": "Roborock Qrevo Curv 2 Flow",
    "localKey": "key123key123key1",
    "productId": "64Pgg7cwjxHqT2qQrEh7Ib",
    "fv": "03.01.71",
    "activeTime": 1749513705,
    "timeZoneId": "Pacific/Auckland",
    "iconUrl": "",
    "share": True,
    "shareTime": 1754789238,
    "online": True,
    "pv": "1.0",
    "tuyaMigrated": False,
    "extra": "{}",
    "sn": "a245_sn",
    "deviceStatus": {"121": 8, "122": 100, "123": 4, "124": 2, "125": 77, "126": 4294965348, "127": 54},
    "silentOtaSwitch": False,
    "f": False,
    "createTime": 1749513706,
    "cid": "DE",
    "shareType": "UNLIMITED_TIME",
}

# HOME_DATA with a245
HOME_DATA_A245 = {
    "id": 123456,
    "name": "My Home",
    "lon": None,
    "lat": None,
    "geoName": None,
    "products": [A245_PRODUCT_DATA],
    "devices": [A245_DEVICE_DATA],
    "receivedDevices": [],
    "rooms": [],
}


def test_login():
    """Test login command with mocked API."""
    print("=" * 60)
    print("TEST: login --email test@example.com")
    print("=" * 60)

    user_data = UserData.from_dict(USER_DATA)

    class FakeApiClient:
        def __init__(self, username: str) -> None:
            self.username = username

        async def request_code_v4(self) -> None:
            pass

        async def code_login_v4(self, code: str) -> UserData:
            return user_data

    import roborock.cli

    original_client = roborock.cli.RoborockApiClient
    roborock.cli.RoborockApiClient = FakeApiClient

    runner = CliRunner()

    # Mock the prompt
    import click

    original_prompt = click.prompt
    click.prompt = lambda *args, **kwargs: "1234"

    try:
        result = runner.invoke(cli, ["login", "--email", "test@example.com"])

        print(f"Exit code: {result.exit_code}")
        print(f"Output:\n{result.output}")
        print(f"Status: {'PASS' if result.exit_code == 0 else 'FAIL'}")

        return result.exit_code == 0
    finally:
        roborock.cli.RoborockApiClient = original_client
        click.prompt = original_prompt


def test_list_devices_without_login():
    """Test list-devices without authentication (should fail)."""
    print("\n" + "=" * 60)
    print("TEST: list-devices (without login)")
    print("=" * 60)

    runner = CliRunner()
    result = runner.invoke(cli, ["list-devices"])

    print(f"Exit code: {result.exit_code}")
    print(f"Output:\n{result.output}")
    print(f"Status: {'PASS (expected error)' if 'login first' in result.output else 'UNEXPECTED'}")

    return "login first" in result.output


def test_discover_without_login():
    """Test discover without authentication (should fail)."""
    print("\n" + "=" * 60)
    print("TEST: discover (without login)")
    print("=" * 60)

    runner = CliRunner()
    result = runner.invoke(cli, ["discover"])

    print(f"Exit code: {result.exit_code}")
    print(f"Output:\n{result.output}")
    print(f"Status: {'PASS (expected error)' if 'login first' in result.output else 'UNEXPECTED'}")

    return "login first" in result.output


def test_list_devices_with_mocked_login():
    """Test list-devices with mocked authenticated context."""
    print("\n" + "=" * 60)
    print("TEST: list-devices (with mocked login)")
    print("=" * 60)

    from unittest.mock import patch, AsyncMock

    runner = CliRunner()

    with runner.isolated_filesystem() as tmp_path:
        # Create mock credential files
        roborock_file = Path(tmp_path) / ".roborock"
        roborock_cache_file = Path(tmp_path) / ".roborock.cache"

        user_data = UserData.from_dict(USER_DATA)
        roborock_file.write_text(json.dumps({"email": "test@example.com", "user_data": user_data.to_dict()}))
        roborock_cache_file.write_text(json.dumps({}))

        # Mock the API client
        class FakeApiClient:
            def __init__(self, user_data: UserData):
                self.user_data = user_data

            async def get_home_data(self):
                # Return mock home data
                from roborock.web_api import HomeData

                return HomeData.from_dict(HOME_DATA_A245)

        # Mock DeviceManager
        class FakeDeviceManager:
            def __init__(self, user_params):
                self.user_params = user_params

            async def get_devices(self):
                from roborock.devices.device import RoborockDevice
                from roborock.data import DeviceData, ProductData

                product_data = ProductData.from_dict(A245_PRODUCT_DATA)
                device_data = DeviceData.from_dict(A245_DEVICE_DATA)

                return []

        with (
            patch("roborock.cli.RoborockContext.roborock_file", roborock_file),
            patch("roborock.cli.RoborockContext.roborock_cache_file", roborock_cache_file),
            patch("roborock.cli.RoborockApiClient") as MockApiClient,
            patch("roborock.cli.create_device_manager") as mock_create_dm,
        ):
            MockApiClient.return_value = AsyncMock()
            MockApiClient.return_value.get_home_data = AsyncMock(return_value=None)

            result = runner.invoke(cli, ["list-devices"])

            print(f"Exit code: {result.exit_code}")
            print(f"Output:\n{result.output}")
            print(f"Status: {'PASS' if result.exit_code == 0 else 'FAIL'}")

            return result.exit_code == 0


def test_help_commands():
    """Test all help commands."""
    commands = [
        ["--help"],
        ["--version"],
        ["login", "--help"],
        ["list-devices", "--help"],
        ["discover", "--help"],
        ["status", "--help"],
        ["command", "--help"],
        ["features", "--help"],
        ["home", "--help"],
        ["consumables", "--help"],
        ["maps", "--help"],
        ["clean-summary", "--help"],
        ["dnd", "--help"],
    ]

    results = []
    for cmd in commands:
        print("\n" + "=" * 60)
        print(f"TEST: {' '.join(cmd)}")
        print("=" * 60)

        runner = CliRunner()
        result = runner.invoke(cli, cmd)

        print(f"Exit code: {result.exit_code}")
        print(f"Output:\n{result.output[:500]}..." if len(result.output) > 500 else f"Output:\n{result.output}")

        passed = result.exit_code == 0
        print(f"Status: {'PASS' if passed else 'FAIL'}")
        results.append((" ".join(cmd), passed))

    return results


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("QREVO CURV 2 FLOW CLI COMMAND TESTS")
    print("Model: roborock.vacuum.a245 (Protocol V1)")
    print("=" * 70)

    # Run all tests
    all_results = []

    # 1. Test help commands
    print("\n\n### HELP COMMANDS ###")
    help_results = test_help_commands()
    all_results.extend(help_results)

    # 2. Test without login
    print("\n\n### WITHOUT AUTHENTICATION ###")
    all_results.append(("discover (no auth)", test_discover_without_login()))
    all_results.append(("list-devices (no auth)", test_list_devices_without_login()))

    # 3. Test login flow
    print("\n\n### LOGIN FLOW ###")
    all_results.append(("login", test_login()))

    # Summary
    print("\n\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, r in all_results if r)
    failed = sum(1 for _, r in all_results if not r)

    for cmd, result in all_results:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {cmd}")

    print(f"\nTotal: {passed} passed, {failed} failed")
    print("=" * 70)
