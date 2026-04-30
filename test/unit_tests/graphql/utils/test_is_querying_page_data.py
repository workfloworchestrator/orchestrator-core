# Copyright 2019-2026 SURF, GÉANT.
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

from unittest.mock import MagicMock

from strawberry.types.nodes import SelectedField

from orchestrator.core.graphql.utils import is_querying_page_data


def test_is_querying_page_data_with_pageinfo_fields():
    info = MagicMock(
        selected_fields=[
            SelectedField(
                name="subscriptions",
                directives={},
                arguments={},
                alias=None,
                selections=[
                    SelectedField(
                        name="pageInfo",
                        directives={},
                        arguments={},
                        alias=None,
                        selections=[
                            SelectedField(name="totalItems", directives={}, arguments={}, alias=None, selections=[]),
                        ],
                    ),
                ],
            ),
        ]
    )

    assert not is_querying_page_data(info)


def test_is_querying_page_data_with_page_fields():
    info = MagicMock(
        selected_fields=[
            SelectedField(
                name="subscriptions",
                directives={},
                arguments={},
                alias=None,
                selections=[
                    SelectedField(
                        name="page",
                        directives={},
                        arguments={},
                        alias=None,
                        selections=[
                            SelectedField(
                                name="subscription_id", directives={}, arguments={}, selections=[], alias=None
                            ),
                            SelectedField(name="description", directives={}, arguments={}, selections=[], alias=None),
                        ],
                    ),
                ],
            ),
        ]
    )

    assert is_querying_page_data(info)


def test_is_querying_page_data_with_page_and_paginfo_fields():
    info = MagicMock(
        selected_fields=[
            SelectedField(
                name="subscriptions",
                directives={},
                arguments={},
                selections=[
                    SelectedField(
                        name="pageInfo",
                        directives={},
                        arguments={},
                        alias=None,
                        selections=[
                            SelectedField(name="totalItems", directives={}, arguments={}, selections=[], alias=None)
                        ],
                    ),
                    SelectedField(
                        name="page",
                        directives={},
                        arguments={},
                        selections=[
                            SelectedField(name="description", directives={}, arguments={}, selections=[], alias=None)
                        ],
                        alias=None,
                    ),
                ],
                alias=None,
            )
        ]
    )

    assert is_querying_page_data(info)
