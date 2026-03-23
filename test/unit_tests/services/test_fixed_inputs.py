from unittest.mock import MagicMock, patch

from orchestrator.services.fixed_inputs import get_fixed_inputs


def _make_mock_fixed_input(name: str = "input_1", value: str = "value_1") -> MagicMock:
    fi = MagicMock()
    fi.name = name
    fi.value = value
    return fi


def test_get_fixed_inputs_returns_all_when_no_filters():
    mock_fi1 = _make_mock_fixed_input("input_1")
    mock_fi2 = _make_mock_fixed_input("input_2")

    mock_session = MagicMock()
    mock_session.scalars.return_value = [mock_fi1, mock_fi2]

    with patch("orchestrator.services.fixed_inputs.db") as mock_db:
        mock_db.session = mock_session
        result = get_fixed_inputs()

    assert result == [mock_fi1, mock_fi2]
    mock_session.scalars.assert_called_once()


def test_get_fixed_inputs_returns_empty_list_when_none_exist():
    mock_session = MagicMock()
    mock_session.scalars.return_value = []

    with patch("orchestrator.services.fixed_inputs.db") as mock_db:
        mock_db.session = mock_session
        result = get_fixed_inputs()

    assert result == []


def test_get_fixed_inputs_with_none_filters_behaves_same_as_no_filters():
    mock_fi = _make_mock_fixed_input("input_1")
    mock_session = MagicMock()
    mock_session.scalars.return_value = [mock_fi]

    with patch("orchestrator.services.fixed_inputs.db") as mock_db:
        mock_db.session = mock_session
        result = get_fixed_inputs(filters=None)

    assert result == [mock_fi]
    mock_session.scalars.assert_called_once()


def test_get_fixed_inputs_applies_where_clause_for_each_filter():
    mock_filter_clause = MagicMock()
    mock_session = MagicMock()
    mock_session.scalars.return_value = []

    with patch("orchestrator.services.fixed_inputs.db") as mock_db:
        with patch("orchestrator.services.fixed_inputs.select") as mock_select:
            mock_stmt = MagicMock()
            mock_select.return_value = mock_stmt
            mock_stmt.where.return_value = mock_stmt
            mock_db.session = mock_session

            get_fixed_inputs(filters=[mock_filter_clause])

    mock_stmt.where.assert_called_once_with(mock_filter_clause)


def test_get_fixed_inputs_applies_multiple_where_clauses():
    filter_a = MagicMock()
    filter_b = MagicMock()
    mock_session = MagicMock()
    mock_session.scalars.return_value = []

    with patch("orchestrator.services.fixed_inputs.db") as mock_db:
        with patch("orchestrator.services.fixed_inputs.select") as mock_select:
            mock_stmt = MagicMock()
            mock_select.return_value = mock_stmt
            mock_stmt.where.return_value = mock_stmt
            mock_db.session = mock_session

            get_fixed_inputs(filters=[filter_a, filter_b])

    assert mock_stmt.where.call_count == 2
    mock_stmt.where.assert_any_call(filter_a)
    mock_stmt.where.assert_any_call(filter_b)


def test_get_fixed_inputs_returns_list_type():
    mock_session = MagicMock()
    mock_session.scalars.return_value = iter([_make_mock_fixed_input()])

    with patch("orchestrator.services.fixed_inputs.db") as mock_db:
        mock_db.session = mock_session
        result = get_fixed_inputs()

    assert isinstance(result, list)
