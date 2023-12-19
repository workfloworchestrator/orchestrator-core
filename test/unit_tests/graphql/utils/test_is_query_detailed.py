from unittest.mock import MagicMock

from strawberry.types.nodes import FragmentSpread, SelectedField

from orchestrator.graphql.utils import is_query_detailed

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
