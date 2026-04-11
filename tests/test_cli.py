import json

from click.testing import CliRunner

from roborock.cli import RoborockContext, cli
from roborock.data import UserData
from tests.mock_data import USER_DATA


def test_login_code_flow_uses_v4(monkeypatch, tmp_path) -> None:
    calls: list[object] = []
    user_data = UserData.from_dict(USER_DATA)

    class FakeApiClient:
        def __init__(self, username: str) -> None:
            self.username = username

        async def request_code_v4(self) -> None:
            calls.append(("request_code_v4", self.username))

        async def code_login_v4(self, code: str) -> UserData:
            calls.append(("code_login_v4", self.username, code))
            return user_data

        async def request_code(self) -> None:
            raise AssertionError("legacy request_code() should not be called")

        async def code_login(self, code: str) -> UserData:
            raise AssertionError("legacy code_login() should not be called")

    monkeypatch.setattr("roborock.cli.RoborockApiClient", FakeApiClient)
    monkeypatch.setattr("roborock.cli.click.prompt", lambda *args, **kwargs: "4123")
    monkeypatch.setattr(RoborockContext, "roborock_file", tmp_path / ".roborock")
    monkeypatch.setattr(RoborockContext, "roborock_cache_file", tmp_path / ".roborock.cache")

    result = CliRunner().invoke(cli, ["login", "--email", "test_user@gmail.com"])

    assert result.exit_code == 0
    assert "Login successful" in result.output
    assert calls == [
        ("request_code_v4", "test_user@gmail.com"),
        ("code_login_v4", "test_user@gmail.com", "4123"),
    ]

    saved_login = json.loads((tmp_path / ".roborock").read_text())
    assert saved_login["email"] == "test_user@gmail.com"
