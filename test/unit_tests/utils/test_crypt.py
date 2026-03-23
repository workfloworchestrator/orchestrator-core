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
from unittest.mock import patch

import pytest

from orchestrator.utils.crypt import Cryptic


@pytest.fixture
def cryptic() -> Cryptic:
    return Cryptic()


class TestCrypticEncryptDecrypt:
    @pytest.mark.parametrize(
        "plaintext",
        [
            "abcd1234",
            "no",
            "Ramesh",
            "bgp password for SAP1",
            "Hello, World!",
            "short",
            "a",
            "with spaces and special chars: !@#$%^&*()",
        ],
        ids=[
            "alphanumeric",
            "two_chars",
            "name",
            "phrase_with_numbers",
            "common_phrase",
            "short_word",
            "single_char",
            "special_chars",
        ],
    )
    def test_round_trip(self, cryptic: Cryptic, plaintext: str) -> None:
        assert cryptic.decrypt(cryptic.encrypt(plaintext)) == plaintext

    def test_ciphertext_starts_with_magic(self, cryptic: Cryptic) -> None:
        ciphertext = cryptic.encrypt("hello")
        assert ciphertext.startswith(Cryptic.MAGIC)

    def test_encrypt_without_salt_produces_valid_ciphertext(self, cryptic: Cryptic) -> None:
        ciphertext = cryptic.encrypt("test")
        assert ciphertext is not None
        assert len(ciphertext) > len(Cryptic.MAGIC)

    def test_encrypt_with_explicit_salt_and_mocked_rand_is_deterministic(self, cryptic: Cryptic) -> None:
        # Encrypt uses _randc for random padding even with a fixed salt.
        # Pin _randc so that the full output becomes deterministic.
        plaintext = "deterministic"
        salt = "Q"
        with patch.object(cryptic, "_randc", side_effect=lambda count=1: "Q" * count):
            first_result = cryptic.encrypt(plaintext, salt=salt)
        with patch.object(cryptic, "_randc", side_effect=lambda count=1: "Q" * count):
            second_result = cryptic.encrypt(plaintext, salt=salt)
        assert first_result == second_result

    def test_decrypt_with_explicit_salt_round_trip(self, cryptic: Cryptic) -> None:
        plaintext = "salted_value"
        salt = "z"
        ciphertext = cryptic.encrypt(plaintext, salt=salt)
        assert cryptic.decrypt(ciphertext) == plaintext

    def test_different_plaintexts_produce_different_ciphertexts(self, cryptic: Cryptic) -> None:
        salt = "Q"
        assert cryptic.encrypt("foo", salt=salt) != cryptic.encrypt("bar", salt=salt)


class TestCrypticDecryptEdgeCases:
    def test_decrypt_none_returns_none(self, cryptic: Cryptic) -> None:
        assert cryptic.decrypt(None) is None

    def test_decrypt_empty_string_returns_none(self, cryptic: Cryptic) -> None:
        assert cryptic.decrypt("") is None

    def test_decrypt_invalid_ciphertext_returns_none(self, cryptic: Cryptic) -> None:
        # "!" is not in the VALID character set, so the regex match fails and decrypt returns None
        assert cryptic.decrypt("!!!invalid!!!") is None

    def test_decrypt_valid_char_but_no_magic_raises(self, cryptic: Cryptic) -> None:
        # A string starting with a VALID char but lacking the $9$ magic prefix causes
        # the internal assert to fire — document that behavior here.
        with pytest.raises(AssertionError):
            cryptic.decrypt("QzF3n6")


class TestCrypticInit:
    def test_num_alpha_is_all_family_chars_joined(self) -> None:
        c = Cryptic()
        expected = "".join(Cryptic.FAMILY)
        assert c.NUM_ALPHA == expected

    def test_alpha_num_is_inverse_of_num_alpha(self) -> None:
        c = Cryptic()
        for idx, char in enumerate(c.NUM_ALPHA):
            assert c.ALPHA_NUM[char] == idx
