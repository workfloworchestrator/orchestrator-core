from orchestrator.utils.datetime import TIMESTAMP_REGEX, timestamp


def test_timestamp_and_regex():
    ts = timestamp()
    assert TIMESTAMP_REGEX.fullmatch(ts)
