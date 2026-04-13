from roborock.cli import _parse_b01_q10_command
from roborock.data.b01_q10.b01_q10_code_mappings import B01_Q10_DP


def test_parse_b01_q10_command_accepts_numeric_codes() -> None:
    assert _parse_b01_q10_command(str(B01_Q10_DP.SEEK.code)) == B01_Q10_DP.SEEK
