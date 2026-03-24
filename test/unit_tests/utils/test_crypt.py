# Copyright 2019-2020 SURF.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for Cryptic encrypt/decrypt: round-trip correctness, magic prefix, edge cases, and lookup table integrity."""

from unittest.mock import patch

import pytest

from orchestrator.utils.crypt import Cryptic


@pytest.fixture
def cryptic() -> Cryptic:
    return Cryptic()


@pytest.mark.parametrize(
    "plaintext",
    [
        pytest.param("abcd1234", id="alphanumeric"),
        pytest.param("a", id="single-char"),
        pytest.param("!@#$%^&*()", id="special-chars"),
        pytest.param("bgp password for SAP1", id="phrase"),
    ],
)
def test_encrypt_decrypt_round_trip(cryptic: Cryptic, plaintext: str) -> None:
    assert cryptic.decrypt(cryptic.encrypt(plaintext)) == plaintext


def test_ciphertext_starts_with_magic(cryptic: Cryptic) -> None:
    assert cryptic.encrypt("hello").startswith(Cryptic.MAGIC)


def test_deterministic_with_fixed_salt_and_randc(cryptic: Cryptic) -> None:
    with patch.object(cryptic, "_randc", side_effect=lambda count=1: "Q" * count):
        first = cryptic.encrypt("test", salt="Q")
    with patch.object(cryptic, "_randc", side_effect=lambda count=1: "Q" * count):
        second = cryptic.encrypt("test", salt="Q")
    assert first == second


def test_different_plaintexts_differ(cryptic: Cryptic) -> None:
    assert cryptic.encrypt("foo", salt="Q") != cryptic.encrypt("bar", salt="Q")


def test_decrypt_with_explicit_salt_round_trip(cryptic: Cryptic) -> None:
    ciphertext = cryptic.encrypt("salted", salt="z")
    assert cryptic.decrypt(ciphertext) == "salted"


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(None, id="none"),
        pytest.param("", id="empty"),
        pytest.param("!!!invalid!!!", id="invalid-chars"),
    ],
)
def test_decrypt_returns_none_for_invalid_input(cryptic: Cryptic, value: object) -> None:
    assert cryptic.decrypt(value) is None


def test_decrypt_without_magic_prefix_raises(cryptic: Cryptic) -> None:
    with pytest.raises(AssertionError):
        cryptic.decrypt("QzF3n6")


def test_alpha_num_is_inverse_of_num_alpha() -> None:
    c = Cryptic()
    for idx, char in enumerate(c.NUM_ALPHA):
        assert c.ALPHA_NUM[char] == idx
