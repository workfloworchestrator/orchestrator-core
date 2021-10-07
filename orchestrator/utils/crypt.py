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

import random
import re
from typing import Dict, List, Optional, Tuple


# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
class Cryptic:

    MAGIC = "$9$"
    MAGIC_SEARCH = r"\$9\$"
    FAMILY = ["QzF3n6/9CAtpu0O", "B1IREhcSyrleKvMW8LXx", "7N-dVbwsY2g4oaJZGUDj", "iHkq.mPf5T"]
    EXTRA: Dict[str, int] = {}
    VALID = ""
    NUM_ALPHA = ""
    ALPHA_NUM: Dict[str, int] = {}
    ENCODING = [[1, 4, 32], [1, 16, 32], [1, 8, 32], [1, 64], [1, 32], [1, 4, 16, 128], [1, 32, 64]]

    # ------------------------------------------------------------------------------
    def __init__(self) -> None:
        for fam in range(len(self.FAMILY)):
            for c in range(len(self.FAMILY[fam])):
                token = self.FAMILY[fam]
                self.EXTRA[token[c]] = 3 - fam

        self.NUM_ALPHA = "".join(self.FAMILY)
        self.VALID = "[" + self.MAGIC + self.NUM_ALPHA + "]"

        for num_alpha in range(len(self.NUM_ALPHA)):
            self.ALPHA_NUM[self.NUM_ALPHA[num_alpha]] = num_alpha

    # ------------------------------------------------------------------------------
    def _randc(self, count: int = 1) -> str:
        ret = ""

        while count > 0:
            ret += self.NUM_ALPHA[random.randint(0, len(self.NUM_ALPHA) - 1)]
            count -= 1

        return ret

    # ------------------------------------------------------------------------------
    def _gap_encode(self, pc: str, prev: str, enc: List[int]) -> str:
        literal_pc = ord(pc)
        crypt = ""
        gaps: List[int] = []

        for mod in reversed(enc):
            gaps.insert(0, int(literal_pc / mod))
            literal_pc %= mod

        for gap in gaps:
            gap += self.ALPHA_NUM[prev] + 1
            prev = self.NUM_ALPHA[gap % len(self.NUM_ALPHA)]
            c = prev
            crypt += c

        return crypt

    # ------------------------------------------------------------------------------
    def encrypt(self, plain: str, salt: Optional[str] = None) -> str:
        if salt is None:
            salt = self._randc(1)
        rand = self._randc(self.EXTRA[salt])
        pos = 0
        prev = salt
        crypt = self.MAGIC + str(salt) + str(rand)

        for p_index in range(len(plain)):
            p = plain[p_index]
            encode = self.ENCODING[pos % len(self.ENCODING)]
            crypt += self._gap_encode(p, prev, encode)
            prev = crypt[-1]
            pos += 1

        return crypt

    # ------------------------------------------------------------------------------
    def _nibble(self, cref: str, length: int) -> Tuple[str, str]:
        nib = cref[0:length]
        cref = cref[length:]

        return nib, cref

    # ------------------------------------------------------------------------------
    def _gap(self, c1: str, c2: str) -> int:
        return ((self.ALPHA_NUM[c2] - self.ALPHA_NUM[c1]) % len(self.NUM_ALPHA)) - 1

    # ------------------------------------------------------------------------------
    def _gap_decode(self, gaps: List[int], dec: List[int]) -> str:
        num = 0
        assert len(gaps) == len(dec)
        for i in range(len(gaps)):
            num += gaps[i] * dec[i]

        return chr(num % 256)

    # ------------------------------------------------------------------------------
    def decrypt(self, crypt: Optional[str]) -> Optional[str]:
        if crypt is None or len(crypt) == 0:
            print("Invalid Crypt")
            return None

        valid_chars = re.compile(self.VALID)
        if valid_chars.match(crypt) is not None:
            match_object = re.match(self.MAGIC_SEARCH, crypt)
            assert match_object
            chars = crypt[match_object.end() :]
            first, chars = self._nibble(chars, 1)
            var, chars = self._nibble(chars, self.EXTRA[first])
            prev = first
            decrypt_str = ""

            while len(chars) > 0:
                decode = self.ENCODING[len(decrypt_str) % len(self.ENCODING)]
                length = len(decode)
                nibble, chars = self._nibble(chars, length)
                gaps = []
                for i in range(len(nibble)):
                    gaps.append(self._gap(prev, nibble[i]))
                    prev = nibble[i]

                decrypt_str += self._gap_decode(gaps, decode)

            return decrypt_str
        else:
            print(crypt + " is invalid !!")
            return None


# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    cryptic = Cryptic()
    print(cryptic.decrypt(cryptic.encrypt("abcd1234")))
    print(cryptic.decrypt(cryptic.encrypt("no")))
    print(cryptic.decrypt(cryptic.encrypt("Ramesh")))
    print(cryptic.encrypt("bgp password for SAP1"))
    print(cryptic.encrypt("bgp password for SAP2"))
