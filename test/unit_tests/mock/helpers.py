from pathlib import Path
from typing import Union

from orchestrator.utils.json import json_dumps, json_loads


def read_file(path: Union[Path, str]) -> str:
    file = Path(__file__).resolve().parent / "data" / path
    with open(file) as f:
        return f.read()


def render(body, **kwargs):
    data = json_loads(body)
    return json_dumps({**data, **kwargs})
