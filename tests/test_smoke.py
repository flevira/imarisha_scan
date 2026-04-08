from imarisha_scan.main import build_home_title


def test_home_title() -> None:
    assert build_home_title() == "Imarisha Scan"
