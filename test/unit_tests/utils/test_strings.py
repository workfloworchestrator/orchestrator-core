from orchestrator.utils.strings import remove_redundant_ws


def test_remove_redundant_ws():
    assert "" == remove_redundant_ws("   ")
    assert "a b c" == remove_redundant_ws(" a  b  c ")
