import pytest
from pydantic.dataclasses import dataclass

from orchestrator.utils.vlans import VlanRanges


def test_vlanranges_instantiation():
    assert VlanRanges() == VlanRanges([])
    assert VlanRanges(None) == VlanRanges([])
    assert VlanRanges("") == VlanRanges([])
    assert VlanRanges(4) == VlanRanges("4")
    assert VlanRanges([10, 12, 13, 14, 15, 16]) == VlanRanges([[10], [12, 16]])
    assert VlanRanges("0") == VlanRanges([(0, 0)]) == VlanRanges([[0]])
    assert VlanRanges("2,4,8") == VlanRanges([(2, 2), (4, 4), (8, 8)]) == VlanRanges([[2], [4], [8]])
    assert VlanRanges("80-120") == VlanRanges([(80, 120)]) == VlanRanges([[80, 120]])
    assert VlanRanges("10,12-16") == VlanRanges([(10, 10), (12, 16)]) == VlanRanges([[10], [12, 16]])
    assert VlanRanges("0-4096") == VlanRanges([[0, 4096]])

    # String interpretation is quite flexible, allowing extra whitespace
    assert VlanRanges("  4   , 6-   10") == VlanRanges("4,6-10")

    # Overlapping ranges will be normalized
    assert VlanRanges("4,6-9,7-10") == VlanRanges("4,6-10")
    assert VlanRanges([[4], [6, 9], [7, 10]]) == VlanRanges([[4], [6, 10]])

    # Non-sensical ranges are not an error perse
    assert VlanRanges("10-1") == VlanRanges("")

    with pytest.raises(ValueError):
        VlanRanges([{}, {}])

    with pytest.raises(ValueError):
        VlanRanges("AAA")

    with pytest.raises(ValueError):
        VlanRanges(object())

    with pytest.raises(ValueError):
        VlanRanges("0-4097")

    with pytest.raises(ValueError):
        VlanRanges("-1-4096")


def test_vlanranges_str_repr():
    vr = VlanRanges("10-14,4,200-256,300-301")

    # `str` version of VlanRanges should be suitable value for constructor, resulting in equivalent object
    assert vr == VlanRanges(str(vr))

    # `repr` version of VlanRanges should be valid Python code resulting in equivalent object
    vr_from_repr = eval(repr(vr), globals(), locals())  # noqa: S307 Use of possibly insecure function
    assert vr_from_repr == vr


def test_vlanranges_eq():
    vr = VlanRanges("10-20")
    assert vr != 1
    assert vr == VlanRanges("10-20")
    assert vr != "foo"


def test_vlanranges_in():
    vr = VlanRanges("10-20")
    assert 10 in vr
    assert 20 in vr
    assert 9 not in vr
    assert 21 not in vr
    assert 0 not in vr


def test_vlanranges_intersects():
    vr = VlanRanges("10-20")
    assert not vr & VlanRanges("8-9")
    assert vr & VlanRanges("9-10")
    assert not vr & VlanRanges("21-23")
    assert vr & VlanRanges("20-23")
    assert vr & VlanRanges("10-20")
    assert vr & VlanRanges("11-19")

    assert vr & VlanRanges("0-3,10,20,21-28")
    assert vr & VlanRanges("0-3,20")
    assert not vr & VlanRanges("0-3,9,21,22-30")


def test_vlanranges_sub():
    vr = VlanRanges("10-20")
    assert vr - VlanRanges("8-9") == VlanRanges("10-20")
    assert vr - VlanRanges("9-10") == VlanRanges("11-20")
    assert vr - VlanRanges("21-23") == VlanRanges("10-20")
    assert vr - VlanRanges("20-23") == VlanRanges("10-19")
    assert vr - VlanRanges("10-20") == VlanRanges("")
    assert vr - VlanRanges("11-19") == VlanRanges("10,20")

    assert vr - VlanRanges("0-3,10,20,21-28") == VlanRanges("11-19")
    assert vr - VlanRanges("0-3,20") == VlanRanges("10-19")
    assert vr - VlanRanges("0-3,9,21,22-30") == VlanRanges("10-20")


def test_vlanranges_sub_int():
    vr = VlanRanges("10-20")
    assert vr - 20 == VlanRanges("10-19")
    assert vr - 10 == VlanRanges("11-20")
    assert vr - 15 == VlanRanges("10-14,16-20")


def test_vlanranges_and():
    vr = VlanRanges("10-20")
    assert vr & VlanRanges("8-9") == VlanRanges("")
    assert vr & VlanRanges("9-10") == VlanRanges("10")
    assert vr & VlanRanges("21-23") == VlanRanges("")
    assert vr & VlanRanges("20-23") == VlanRanges("20")
    assert vr & VlanRanges("10-20") == VlanRanges("10-20")
    assert vr & VlanRanges("11-19") == VlanRanges("11-19")

    assert vr & VlanRanges("0-3,10,20,21-28") == VlanRanges("10,20")
    assert vr & VlanRanges("0-3,20") == VlanRanges("20")
    assert vr & VlanRanges("0-3,9,21,22-30") == VlanRanges("")


def test_vlanranges_or():
    vr = VlanRanges("10-20")
    assert vr | VlanRanges("8-9") == VlanRanges("8-20")
    assert vr | VlanRanges("9-10") == VlanRanges("9-20")
    assert vr | VlanRanges("21-23") == VlanRanges("10-23")
    assert vr | VlanRanges("20-23") == VlanRanges("10-23")
    assert vr | VlanRanges("10-20") == VlanRanges("10-20")
    assert vr | VlanRanges("11-19") == VlanRanges("10-20")

    assert vr | VlanRanges("0-3,10,20,21-28") == VlanRanges("0-3,10-28")
    assert vr | VlanRanges("0-3,20") == VlanRanges("0-3,10-20")
    assert vr | VlanRanges("0-3,9,21,22-30") == VlanRanges("0-3,9-30")


def test_vlanranges_isdisjoint():
    vr = VlanRanges("10-20")
    assert vr.isdisjoint(VlanRanges("8-9"))
    assert not vr.isdisjoint(VlanRanges("9-10"))
    assert vr.isdisjoint(VlanRanges("21-23"))
    assert not vr.isdisjoint(VlanRanges("20-23"))
    assert not vr.isdisjoint(VlanRanges("10-20"))
    assert not vr.isdisjoint(VlanRanges("11-19"))

    assert not vr.isdisjoint(VlanRanges("0-3,10,20,21-28"))
    assert not vr.isdisjoint(VlanRanges("0-3,20"))
    assert vr.isdisjoint(VlanRanges("0-3,9,21,22-30"))


def test_vlanranges_union():
    vr = VlanRanges("10-20")
    # with iterable
    assert vr == VlanRanges().union(VlanRanges("10-15"), [16, 17, 18], (19,), VlanRanges(20))

    # single arg
    assert vr == VlanRanges("10-19").union(VlanRanges(20))


def test_vlanranges_xor():
    vr = VlanRanges("10-20")
    assert vr ^ VlanRanges("8-9") == VlanRanges("8-20")
    assert vr ^ VlanRanges("9-10") == VlanRanges("9,11-20")
    assert vr ^ VlanRanges("21-23") == VlanRanges("10-23")
    assert vr ^ VlanRanges("20-23") == VlanRanges("10-19,21-23")
    assert vr ^ VlanRanges("10-20") == VlanRanges("")
    assert vr ^ VlanRanges("11-19") == VlanRanges("10,20")

    assert vr ^ VlanRanges("0-3,10,20,21-28") == VlanRanges("0-3,11-19,21-28")
    assert vr ^ VlanRanges("0-3,20") == VlanRanges("0-3,10-19")
    assert vr ^ VlanRanges("0-3,9,21,22-30") == VlanRanges("0-3,9-30")


def test_vlanranges_lt():
    vr = VlanRanges("10-20")
    assert not VlanRanges("8-9") < vr
    assert not VlanRanges("9-10") < vr
    assert not VlanRanges("21-23") < vr
    assert not VlanRanges("20-23") < vr
    assert not VlanRanges("10-20") < vr
    assert VlanRanges("11-19") < vr
    assert not VlanRanges("9-21") < vr

    assert not VlanRanges("0-3,10,20,21-28") < vr
    assert not VlanRanges("0-3,20") < vr
    assert not VlanRanges("0-3,9,21,22-30") < vr


def test_vlanranges_ge():
    vr = VlanRanges("10-20")
    assert not VlanRanges("8-9") >= vr
    assert not VlanRanges("9-10") >= vr
    assert not VlanRanges("21-23") >= vr
    assert not VlanRanges("20-23") >= vr
    assert VlanRanges("10-20") >= vr
    assert not VlanRanges("11-19") >= vr
    assert VlanRanges("9-21") >= vr

    assert not VlanRanges("0-3,10,20,21-28") >= vr
    assert not VlanRanges("0-3,20") >= vr
    assert not VlanRanges("0-3,9,21,22-30") >= vr


def test_vlanranges_hash():
    vr = VlanRanges("10-14,4,200-256")
    # Just making sure it doesn't raise an exception. Which, BTW will be raised, should the internal representation
    # be changed to a mutable data structure.
    assert hash(vr)


def test_vlanranges_len():
    assert len(VlanRanges(1)) == 1
    assert len(VlanRanges("0-4096")) == 4097
    assert len(VlanRanges("0-5,10-15")) == 12


def test_vlanranges_serialization_deserialization():
    vr = VlanRanges("3,4-10")
    vr2 = VlanRanges(vr.__json__())
    assert vr == vr2


def test_vlanranges_validations():
    # Negative values, however, are an error
    with pytest.raises(ValueError):
        VlanRanges("-10")

    with pytest.raises(ValueError):
        VlanRanges("fubar")

    # Pydantic validation support is present
    @dataclass
    class TestVlanRanges:
        vlanrange: VlanRanges

    assert TestVlanRanges(vlanrange="12").vlanrange == VlanRanges(12)
    assert TestVlanRanges(vlanrange=VlanRanges(12)).vlanrange == VlanRanges(12)

    with pytest.raises(ValueError):
        TestVlanRanges(vlanrange="bla")

    with pytest.raises(ValueError):
        TestVlanRanges(vlanrange="-30")

    with pytest.raises(ValueError):
        TestVlanRanges(vlanrange="5000")
