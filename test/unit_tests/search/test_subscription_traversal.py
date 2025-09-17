from orchestrator.search.core.types import EntityType
from orchestrator.search.indexing.traverse import SubscriptionTraverser
from orchestrator.search.indexing.registry import ENTITY_CONFIG_REGISTRY


class TestSubscriptionTraverser:
    """Integration tests that the new model-first traversal works end-to-end."""

    def _assert_traverse_fields_match(
        self, mock_load_model, mock_db_subscription, subscription_instance, expected_fields
    ) -> None:
        """Helper method to test subscription traversal and field matching."""
        mock_load_model.return_value = subscription_instance
        config = ENTITY_CONFIG_REGISTRY[EntityType.SUBSCRIPTION]

        model = SubscriptionTraverser._load_model(sub=mock_db_subscription)
        extracted_fields = list(SubscriptionTraverser.traverse(model, path=config.root_name))

        expected_set = set(expected_fields)
        actual_set = set(extracted_fields)

        missing_fields = expected_set - actual_set
        extra_fields = actual_set - expected_set

        assert not missing_fields, f"Missing fields: {missing_fields}"
        assert not extra_fields, f"Extra fields: {extra_fields}"
        assert len(extracted_fields) == len(expected_fields)

    def test_traverse_with_real_subscription_flow(
        self, mock_load_model, mock_db_subscription, subscription_instance, expected_traverse_fields
    ) -> None:
        """
        Verifies that traverse() walks the Pydantic subscription model and
        emits the expected searchable fields and types.
        """
        self._assert_traverse_fields_match(
            mock_load_model, mock_db_subscription, subscription_instance, expected_traverse_fields
        )

    def test_traverse_simple_direct_block(
        self, mock_load_model, mock_db_subscription, simple_subscription_instance, simple_expected_fields
    ) -> None:
        """Test traversing a simple subscription with direct block access (no lists)."""
        self._assert_traverse_fields_match(
            mock_load_model, mock_db_subscription, simple_subscription_instance, simple_expected_fields
        )

    def test_traverse_nested_blocks(
        self, mock_load_model, mock_db_subscription, nested_subscription_instance, nested_expected_fields
    ) -> None:
        """Test traversing deeply nested blocks (block containing block containing block)."""
        self._assert_traverse_fields_match(
            mock_load_model, mock_db_subscription, nested_subscription_instance, nested_expected_fields
        )

    def test_traverse_computed_property(
        self,
        mock_load_model,
        mock_db_subscription,
        computed_property_subscription_instance,
        computed_property_expected_fields,
    ) -> None:
        """Test traversing a subscription with computed property fields."""
        self._assert_traverse_fields_match(
            mock_load_model,
            mock_db_subscription,
            computed_property_subscription_instance,
            computed_property_expected_fields,
        )
