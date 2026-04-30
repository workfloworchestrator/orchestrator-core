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

from strawberry.types.nodes import FragmentSpread, SelectedField

from orchestrator.core.graphql.utils import is_query_detailed

is_test_query_detailed = is_query_detailed(("basic", "name"))


def test_is_test_query_detailed_with_basic_fields():
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
                            SelectedField(name="basic", directives={}, arguments={}, alias=None, selections=[]),
                            SelectedField(name="name", directives={}, arguments={}, alias=None, selections=[]),
                        ],
                    ),
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

    assert not is_test_query_detailed(info)


def test_is_test_query_detailed_with_basic_gragment_field():
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
                            FragmentSpread(
                                name="fragment",
                                type_condition="graphql type",
                                directives={},
                                selections=[
                                    SelectedField(name="basic", directives={}, arguments={}, selections=[], alias=None),
                                    SelectedField(name="name", directives={}, arguments={}, selections=[], alias=None),
                                ],
                            )
                        ],
                    ),
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

    assert not is_test_query_detailed(info)


def test_is_test_query_detailed_with_detailed_fields():
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
                            SelectedField(name="detailed", directives={}, arguments={}, alias=None, selections=[]),
                            SelectedField(name="not basic", directives={}, arguments={}, alias=None, selections=[]),
                        ],
                    ),
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

    assert is_test_query_detailed(info)


def test_is_test_query_detailed_with_detailed_fragment_field():
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
                            FragmentSpread(
                                name="fragment",
                                type_condition="graphql type",
                                directives={},
                                selections=[
                                    SelectedField(
                                        name="detailed", directives={}, arguments={}, alias=None, selections=[]
                                    ),
                                    SelectedField(
                                        name="not basic", directives={}, arguments={}, alias=None, selections=[]
                                    ),
                                ],
                            )
                        ],
                    ),
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

    assert is_test_query_detailed(info)


def test_is_test_query_detailed_with_basic_and_detailed_fields():
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
                            SelectedField(name="basic", directives={}, arguments={}, alias=None, selections=[]),
                            SelectedField(name="name", directives={}, arguments={}, alias=None, selections=[]),
                            SelectedField(name="detailed", directives={}, arguments={}, alias=None, selections=[]),
                            SelectedField(name="not basic", directives={}, arguments={}, alias=None, selections=[]),
                        ],
                    ),
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

    assert is_test_query_detailed(info)
