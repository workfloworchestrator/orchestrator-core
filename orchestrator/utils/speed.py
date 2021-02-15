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

from math import floor, log
from typing import Union


def format_bandwidth(mbits: int, short: bool = False) -> str:
    """Format bandwidth with unit designator (eg, Mbit/s or M).

    * It supports units up to and including Petabit.
    * If it cannot convert the number to an integral one, it will allow for 1 decimal.
    * Negative bandwidths will always return 0 Mbit/s or 0 M

    Examples::

        >>> format_bandwidth(40)
        '40 Mbit/s'
        >>> format_bandwidth(40, True)
        '40M'
        >>> format_bandwidth(10000)
        '10 Gbit/s'
        >>> format_bandwidth(10000, True)
        '10G'
        >>> format_bandwidth(1300)
        '1.3 Gbit/s'
        >>> format_bandwidth(0)
        '0 Mbit/s'
        >>> format_bandwidth(-100)
        '0 Mbit/s'

    Args:
        mbits: number of mbits
        short: boolean indicating whether to use 'M', 'G' or 'Mbit/s' or 'Gbit/s', etc

    Returns:
        Formatted number with unit designator.

    """
    unit_fmt, separator = ("short", "") if short else ("long", " ")
    units = {"short": ["M", "G", "T", "P"], "long": ["Mbit/s", "Gbit/s", "Tbit/s", "Pbit/s"]}
    base = 1_000
    magnitude = 0
    number = "0"
    if mbits > 0:
        magnitude = floor(log(mbits, base))
        number = f"{(mbits / base ** magnitude):.1f}"
    if number.endswith(".0"):
        number = number[:-2]
    return f"{number}{separator}{units[unit_fmt][magnitude]}"


def speed_humanize(bandwidth: Union[int, str], short: bool = False) -> str:
    if isinstance(bandwidth, str) and "," in bandwidth:
        return ",".join(map(speed_humanize, bandwidth.split(",")))
    try:
        speed = int(bandwidth)
    except ValueError:
        return str(bandwidth)
    except TypeError:
        return str(bandwidth)
    return format_bandwidth(speed, short=short)
