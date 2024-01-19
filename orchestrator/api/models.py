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


from collections.abc import Iterable
from copy import deepcopy
from datetime import datetime
from http import HTTPStatus
from typing import Any
from uuid import UUID

from dateutil.parser import isoparse
from more_itertools import flatten
from pydantic import BaseModel
from sqlalchemy import Column

from orchestrator.api.error_handling import raise_status
from orchestrator.db import (
    FixedInputTable,
    ProcessStepTable,
    ProcessSubscriptionTable,
    ProductBlockTable,
    ProductTable,
    ResourceTypeTable,
    SubscriptionInstanceTable,
    SubscriptionInstanceValueTable,
    WorkflowTable,
    db,
)
from orchestrator.db.database import BaseModel as DbBaseModel


def validate(cls: type[DbBaseModel], json_dict: dict, is_new_instance: bool = True) -> dict:
    def is_required(v: Column) -> bool:
        return not v.nullable and (not v.server_default or v.primary_key)

    table = cls.__table__  # type: ignore[attr-defined]
    required_columns = {k: v for k, v, *_ in table.columns._collection if is_required(v)}

    required_attributes: Iterable[str] = required_columns.keys()
    if is_new_instance:
        required_attributes = (key for key in required_attributes if not required_columns[key].primary_key)

    missing_attributes = [key for key in required_attributes if key not in json_dict]
    if missing_attributes:
        detail = f"Missing attributes '{', '.join(missing_attributes)}' for {cls.__name__}"
        raise_status(HTTPStatus.BAD_REQUEST, detail=detail)
    return json_dict


def _merge(cls: type[DbBaseModel], d: dict) -> None:
    o = cls(**d)
    db.session.merge(o)
    db.session.commit()


def save(cls: type[DbBaseModel], json_data: BaseModel) -> None:
    try:
        json_dict = transform_json(json_data.model_dump())
        _merge(cls, json_dict)
    except Exception as e:
        raise_status(HTTPStatus.INTERNAL_SERVER_ERROR, str(e))


def create_or_update(cls: type, obj: BaseModel) -> None:
    try:
        json_dict = transform_json(obj.model_dump())
        _merge(cls, json_dict)
    except Exception as e:
        raise_status(HTTPStatus.INTERNAL_SERVER_ERROR, str(e))


def update(cls: type[DbBaseModel], base_model: BaseModel) -> None:
    json_dict = transform_json(base_model.model_dump())
    table = cls.__table__  # type: ignore[attr-defined]
    pk = list({k: v for k, v, *_ in table.columns._collection if v.primary_key}.keys())[0]
    instance = cls.query.filter(cls.__dict__[pk] == json_dict[pk])
    if not instance:
        raise_status(HTTPStatus.NOT_FOUND)
    json_dict = validate(cls, json_dict, is_new_instance=False)
    try:
        _merge(cls, json_dict)
    except Exception as e:
        raise_status(HTTPStatus.INTERNAL_SERVER_ERROR, str(e))


def delete(cls: type[DbBaseModel], primary_key: UUID) -> None:
    table = cls.__table__  # type: ignore[attr-defined]
    pk = list({k: v for k, v, *_ in table.columns._collection if v.primary_key}.keys())[0]
    row_count = cls.query.filter(cls.__dict__[pk] == primary_key).delete()
    db.session.commit()
    if row_count > 0:
        return
    raise_status(HTTPStatus.NOT_FOUND)


deserialization_mapping = {
    "steps": ProcessStepTable,
    "subscriptions": ProcessSubscriptionTable,
    "product_blocks": ProductBlockTable,
    "fixed_inputs": FixedInputTable,
    "resource_types": ResourceTypeTable,
    "instances": SubscriptionInstanceTable,
    "values": SubscriptionInstanceValueTable,
    "products": ProductTable,
    "workflows": WorkflowTable,
}

forbidden_fields = ["created_at"]
date_fields = ["end_date"]


def cleanse_json(json_dict: dict) -> None:
    copy_json_dict = deepcopy(json_dict)
    for k in copy_json_dict.keys():
        if copy_json_dict[k] is None:
            del json_dict[k]
    for forbidden in forbidden_fields:
        if forbidden in json_dict:
            del json_dict[forbidden]
        rel: dict
        for rel in flatten(list(filter(lambda i: isinstance(i, list), json_dict.values()))):
            cleanse_json(rel)


def parse_date_fields(json_dict: dict) -> None:
    for date_field in date_fields:
        if date_field in json_dict:
            val = json_dict[date_field]
            if isinstance(val, float) or isinstance(val, int):
                json_dict[date_field] = datetime.fromtimestamp(val / 1e3)
            if isinstance(val, str):
                timestamp = isoparse(val)
                assert timestamp.tzinfo is not None, "All timestamps should contain timezone information."  # noqa: S101
                json_dict[date_field] = timestamp
        rel: dict
        for rel in flatten(list(filter(lambda i: isinstance(i, list), json_dict.values()))):
            parse_date_fields(rel)


def transform_json(json_dict: dict) -> dict:
    def _contains_list(coll: Iterable[Any]) -> bool:
        return len(list(filter(lambda item: isinstance(item, list), coll))) > 0

    def _do_transform(items: Iterable[tuple[str, Any]]) -> dict:
        return dict(map(_parse, items))

    def _parse(item: tuple[str, Any]) -> tuple[str, Any]:
        if isinstance(item[1], list):
            cls = deserialization_mapping[item[0]]
            return item[0], list(map(lambda i: cls(**_do_transform(i.items())), item[1]))
        return item

    cleanse_json(json_dict)
    parse_date_fields(json_dict)

    if _contains_list(json_dict.values()):
        return _do_transform(json_dict.items())

    return json_dict
