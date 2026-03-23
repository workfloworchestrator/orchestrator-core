from unittest.mock import MagicMock, patch

from orchestrator.services.resource_types import get_resource_types


def _make_mock_resource_type(resource_type: str = "rt_1", description: str = "A resource type") -> MagicMock:
    rt = MagicMock()
    rt.resource_type = resource_type
    rt.description = description
    return rt


def test_get_resource_types_returns_all_when_no_filters():
    mock_rt1 = _make_mock_resource_type("rt_1")
    mock_rt2 = _make_mock_resource_type("rt_2")

    mock_session = MagicMock()
    mock_session.scalars.return_value = [mock_rt1, mock_rt2]

    with patch("orchestrator.services.resource_types.db") as mock_db:
        mock_db.session = mock_session
        result = get_resource_types()

    assert result == [mock_rt1, mock_rt2]
    mock_session.scalars.assert_called_once()


def test_get_resource_types_returns_empty_list_when_none_exist():
    mock_session = MagicMock()
    mock_session.scalars.return_value = []

    with patch("orchestrator.services.resource_types.db") as mock_db:
        mock_db.session = mock_session
        result = get_resource_types()

    assert result == []


def test_get_resource_types_with_none_filters_behaves_same_as_no_filters():
    mock_rt = _make_mock_resource_type("rt_1")
    mock_session = MagicMock()
    mock_session.scalars.return_value = [mock_rt]

    with patch("orchestrator.services.resource_types.db") as mock_db:
        mock_db.session = mock_session
        result = get_resource_types(filters=None)

    assert result == [mock_rt]
    mock_session.scalars.assert_called_once()


def test_get_resource_types_applies_where_clause_for_each_filter():
    mock_filter_clause = MagicMock()
    mock_session = MagicMock()
    mock_session.scalars.return_value = []

    with patch("orchestrator.services.resource_types.db") as mock_db:
        with patch("orchestrator.services.resource_types.select") as mock_select:
            mock_stmt = MagicMock()
            mock_select.return_value = mock_stmt
            mock_stmt.where.return_value = mock_stmt
            mock_db.session = mock_session

            get_resource_types(filters=[mock_filter_clause])

    mock_stmt.where.assert_called_once_with(mock_filter_clause)


def test_get_resource_types_applies_multiple_where_clauses():
    filter_a = MagicMock()
    filter_b = MagicMock()
    mock_session = MagicMock()
    mock_session.scalars.return_value = []

    with patch("orchestrator.services.resource_types.db") as mock_db:
        with patch("orchestrator.services.resource_types.select") as mock_select:
            mock_stmt = MagicMock()
            mock_select.return_value = mock_stmt
            mock_stmt.where.return_value = mock_stmt
            mock_db.session = mock_session

            get_resource_types(filters=[filter_a, filter_b])

    assert mock_stmt.where.call_count == 2
    mock_stmt.where.assert_any_call(filter_a)
    mock_stmt.where.assert_any_call(filter_b)


def test_get_resource_types_returns_list_type():
    mock_session = MagicMock()
    mock_session.scalars.return_value = iter([_make_mock_resource_type()])

    with patch("orchestrator.services.resource_types.db") as mock_db:
        mock_db.session = mock_session
        result = get_resource_types()

    assert isinstance(result, list)
