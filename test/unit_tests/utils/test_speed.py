from orchestrator.utils.speed import speed_humanize


def test_speed_humanize_long():
    assert speed_humanize(0) == "0 Mbit/s"
    assert speed_humanize(1) == "1 Mbit/s"
    assert speed_humanize(1000) == "1 Gbit/s"
    assert speed_humanize(1000000) == "1 Tbit/s"
    assert speed_humanize(1000000000) == "1 Pbit/s"
    assert speed_humanize("1000") == "1 Gbit/s"
    assert speed_humanize("750") == "750 Mbit/s"
    assert speed_humanize("2 Gbit/s") == "2 Gbit/s"

    class Foo:
        def __str__(self) -> str:
            return "bar"

    assert speed_humanize(Foo()) == "bar"


def test_speed_humanize_short():
    assert speed_humanize(0, True) == "0M"
    assert speed_humanize(1, True) == "1M"
    assert speed_humanize(1000, True) == "1G"
    assert speed_humanize(1000000, True) == "1T"
    assert speed_humanize(1000000000, True) == "1P"
    assert speed_humanize("1000", True) == "1G"
    assert speed_humanize("750", True) == "750M"
    assert speed_humanize("2 Gbit/s", True) == "2 Gbit/s"


def test_speed_humanize_elan_bandwidth():
    res = speed_humanize("1000,750,1000")
    assert res == "1 Gbit/s,750 Mbit/s,1 Gbit/s"
