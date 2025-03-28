from pydantic import computed_field

from orchestrator.domain.base import DomainModel


def test_serializable_property():
    class DerivedDomainModel(DomainModel):
        @computed_field  # type: ignore[misc]
        @property
        def double_int_field(self) -> int:
            # This property is serialized
            return 2 * self.int_field

        @property
        def triple_int_field(self) -> int:
            # This property is not serialized
            return 3 * self.int_field

        int_field: int

    block = DerivedDomainModel(int_field=13)

    assert block.model_dump() == {"int_field": 13, "double_int_field": 26}


def test_inherited_serializable_property():
    class ProvisioningDomainModel(DomainModel):
        @computed_field  # type: ignore[misc]
        @property
        def double_int_field(self) -> int:
            return 2 * self.int_field

        @computed_field  # type: ignore[misc]
        @property
        def triple_int_field(self) -> int:
            return 3 * self.int_field

        int_field: int

    class ActiveDomainModel(ProvisioningDomainModel):
        @computed_field  # type: ignore[misc]
        @property
        def triple_int_field(self) -> int:
            # override the base property
            return 30 * self.int_field

    block = ActiveDomainModel(int_field=1)

    assert block.model_dump() == {"int_field": 1, "double_int_field": 2, "triple_int_field": 30}


def test_nested_serializable_property():
    """Ensure that nested serializable property's are included in the serialized model."""

    class DerivedDomainModel(DomainModel):
        @computed_field  # type: ignore[misc]
        @property
        def double_int_field(self) -> int:
            # This property is serialized
            return 2 * self.int_field

        int_field: int

    class ParentDomainModel(DomainModel):
        derived: DerivedDomainModel

    model = ParentDomainModel(derived=DerivedDomainModel(int_field=13))

    assert model.model_dump() == {"derived": {"int_field": 13, "double_int_field": 26}}
