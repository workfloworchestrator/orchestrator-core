from typing import List, Union, Annotated, Literal
from datetime import datetime
from uuid import UUID
from enum import Enum, IntEnum

from pydantic import computed_field, AfterValidator
from annotated_types import Len
from strawberry.experimental.pydantic import type as strawberry_type

from orchestrator.domain.base import ProductBlockModel


class StatusEnum(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class PriorityIntEnum(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


def validate_mtu(val: int) -> int:
    if val not in (1500, 9000):
        raise ValueError("MTU must be either 1500 or 9000")
    return val


MTU = Annotated[int, AfterValidator(validate_mtu)]
MTUChoice = Literal[1500, 9000]
RequiredIntList = Annotated[list[int], Len(min_length=1)]


class BasicBlock(ProductBlockModel):
    """Basic block with fundamental field types for testing."""

    name: str
    value: int
    enabled: bool
    ratio: float
    created_at: datetime


class ListBlock(ProductBlockModel):
    """Block containing various list types for testing list traversal."""

    # Integer lists
    int_list_old: List[int]
    int_list_new: list[int]

    # Float and boolean lists
    float_list: list[float]
    bool_list: list[bool]

    # Enum lists
    status_list: list[StatusEnum]
    priority_list: list[PriorityIntEnum]

    # Nested lists
    nested_int_lists: list[list[int]]

    # Annotated types
    required_ids: RequiredIntList
    mtu_values: list[MTU]


class UnionBlock(ProductBlockModel):
    """Block with union and optional types for testing type resolution."""

    # Basic union types
    optional_id: int | None
    id_or_name: str | int

    # Literal and annotated types
    mtu_choice: MTUChoice
    validated_mtu: MTU


class EnumBlock(ProductBlockModel):
    """Block with enum fields for testing enum traversal."""

    status: StatusEnum
    priority: PriorityIntEnum


class ComputedBlock(ProductBlockModel):
    """Block with computed properties for testing computed field traversal."""

    device_id: int
    device_name: str
    status: str

    @computed_field  # type: ignore[prop-decorator]
    @property
    def display_name(self) -> str:
        return f"{self.device_name} ({self.device_id})"


class NestedBlock(ProductBlockModel):
    """Block that contains other blocks for testing nested traversal."""

    basic_block: BasicBlock
    list_blocks: list[BasicBlock]


class InnerBlock(ProductBlockModel):
    """Inner block for testing nested traversal."""

    inner_name: str
    inner_value: int
    status: StatusEnum


class MiddleBlock(ProductBlockModel):
    """Middle block containing another block."""

    middle_name: str
    inner_block: InnerBlock
    middle_count: int


class OuterBlock(ProductBlockModel):
    """Outer block containing nested blocks."""

    outer_name: str
    middle_block: MiddleBlock
    outer_total: int


class ContainerBlock(ProductBlockModel):
    """Complex container block combining multiple block types."""

    singular_block: BasicBlock

    # Basic
    customer_ptp_ipv4_secondary_ipam_ids: List[int]
    string_field: str
    int_field: int
    block_list: List[BasicBlock]
    modern_float_list: list[float]
    modern_bool_list: list[bool]
    # Enums
    status: StatusEnum
    priority: PriorityIntEnum
    status_list: list[StatusEnum]
    priority_list: list[PriorityIntEnum]
    # Nested lists
    nested_int_lists: list[list[int]]
    # Union types
    optional_primary_id: int | None
    id_or_name: int | str
    # Union of blocks
    union_block: Union[BasicBlock, UnionBlock, None]
    # Annotated and literal types
    required_config_ids: RequiredIntList
    mtu_choice: MTUChoice
    customer_ipv4_mtu: MTU
    mtu_values: list[MTU]

    float_field: float
    last_seen: datetime


class ContainerListBlock(ProductBlockModel):
    """Block containing a list of containers."""

    endpoints: list[ContainerBlock]
