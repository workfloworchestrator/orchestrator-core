from orchestrator.utils.speed import speed_humanize


def test_speed_humanize_gb():
    res = speed_humanize("1000")
    assert res == "1 Gbit/s"


def test_speed_humanize_happy_flow():
    res = speed_humanize("750")
    assert res == "750 Mbit/s"


def test_speed_humanize():
    res = speed_humanize(1000)
    assert res == "1 Gbit/s"


def test_speed_humanize_elan_bandwidth():
    res = speed_humanize("1000,750,1000")
    assert res == "1 Gbit/s,750 Mbit/s,1 Gbit/s"
