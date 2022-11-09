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

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

import sqlalchemy
import structlog
from more_itertools import first_true
from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    TypeDecorator,
    text,
)
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.engine import Dialect
from sqlalchemy.exc import DontWrapMixin
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.orderinglist import ordering_list
from sqlalchemy.orm import backref, deferred, object_session, relationship
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy_utils import TSVectorType, UUIDType

from orchestrator.config.assignee import Assignee
from orchestrator.db.database import BaseModel, SearchQuery
from orchestrator.targets import Target
from orchestrator.utils.datetime import nowtz
from orchestrator.version import GIT_COMMIT_HASH

logger = structlog.get_logger(__name__)

TAG_LENGTH = 20
STATUS_LENGTH = 255


class UtcTimestampException(Exception, DontWrapMixin):
    pass


class UtcTimestamp(TypeDecorator):
    """Timestamps in UTC.

    This column type always returns timestamps with the UTC timezone, regardless of the database/connection time zone
    configuration. It also guards against accidentally trying to store Python naive timestamps (those without a time
    zone).
    """

    impl = sqlalchemy.types.TIMESTAMP(timezone=True)
    cache_ok = False

    def process_bind_param(self, value: Optional[datetime], dialect: Dialect) -> Optional[datetime]:
        if value is not None:
            if value.tzinfo is None:
                raise UtcTimestampException(f"Expected timestamp with tzinfo. Got naive timestamp {value!r} instead")
        return value

    def process_result_value(self, value: Optional[datetime], dialect: Dialect) -> Optional[datetime]:
        if value is not None:
            return value.astimezone(timezone.utc)
        return value


class ProcessTable(BaseModel):
    __tablename__ = "processes"

    pid = Column(UUIDType, server_default=text("uuid_generate_v4()"), primary_key=True, index=True)
    workflow = Column(String(255), nullable=False)
    assignee = Column(String(50), server_default=Assignee.SYSTEM, nullable=False)
    last_status = Column(String(50), nullable=False)
    last_step = Column(String(255), nullable=True)
    started_at = Column(UtcTimestamp, server_default=text("current_timestamp()"), nullable=False)
    last_modified_at = Column(UtcTimestamp, server_default=text("current_timestamp()"), onupdate=nowtz, nullable=False)
    failed_reason = Column(Text())
    traceback = Column(Text())
    created_by = Column(String(255), nullable=True)
    is_task = Column(Boolean, nullable=False, server_default=text("false"), index=True)
    steps = relationship(
        "ProcessStepTable", cascade="delete", passive_deletes=True, order_by="asc(ProcessStepTable.executed_at)"
    )
    process_subscriptions = relationship("ProcessSubscriptionTable", lazy=True, passive_deletes=True)
    subscriptions = association_proxy("process_subscriptions", "subscription")


class ProcessStepTable(BaseModel):
    __tablename__ = "process_steps"
    stepid = Column(UUIDType, server_default=text("uuid_generate_v4()"), primary_key=True)
    pid = Column(UUIDType, ForeignKey("processes.pid", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(), nullable=False)
    status = Column(String(50), nullable=False)
    state = Column(pg.JSONB(), nullable=False)
    created_by = Column(String(255), nullable=True)
    executed_at = Column(UtcTimestamp, server_default=text("statement_timestamp()"), nullable=False)
    commit_hash = Column(String(40), nullable=True, default=GIT_COMMIT_HASH)


class ProcessSubscriptionTable(BaseModel):
    __tablename__ = "processes_subscriptions"
    id = Column(UUIDType, server_default=text("uuid_generate_v4()"), primary_key=True)
    pid = Column(UUIDType, ForeignKey("processes.pid", ondelete="CASCADE"), nullable=False, index=True)
    process = relationship("ProcessTable", back_populates="process_subscriptions")
    subscription_id = Column(UUIDType, ForeignKey("subscriptions.subscription_id"), nullable=False, index=True)
    subscription = relationship("SubscriptionTable", lazy=True)
    created_at = Column(UtcTimestamp, server_default=text("current_timestamp()"), nullable=False)
    workflow_target = Column(String(255), nullable=False, server_default=Target.CREATE)


processes_subscriptions_ix = Index(
    "processes_subscriptions_ix", ProcessSubscriptionTable.pid, ProcessSubscriptionTable.subscription_id
)

product_product_block_association = Table(
    "product_product_blocks",
    BaseModel.metadata,
    Column("product_id", UUIDType, ForeignKey("products.product_id", ondelete="CASCADE"), primary_key=True),
    Column(
        "product_block_id",
        UUIDType,
        ForeignKey("product_blocks.product_block_id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


product_block_resource_type_association = Table(
    "product_block_resource_types",
    BaseModel.metadata,
    Column(
        "product_block_id",
        UUIDType,
        ForeignKey("product_blocks.product_block_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "resource_type_id",
        UUIDType,
        ForeignKey("resource_types.resource_type_id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


product_workflows_association = Table(
    "products_workflows",
    BaseModel.metadata,
    Column("product_id", UUIDType, ForeignKey("products.product_id", ondelete="CASCADE"), primary_key=True),
    Column("workflow_id", UUIDType, ForeignKey("workflows.workflow_id", ondelete="CASCADE"), primary_key=True),
)


class ProductTable(BaseModel):
    __tablename__ = "products"

    product_id = Column(UUIDType, server_default=text("uuid_generate_v4()"), primary_key=True)
    name = Column(String(), nullable=False, unique=True)
    description = Column(Text(), nullable=False)
    product_type = Column(String(255), nullable=False)
    tag = Column(String(TAG_LENGTH), nullable=False, index=True)
    status = Column(String(STATUS_LENGTH), nullable=False)
    created_at = Column(UtcTimestamp, nullable=False, server_default=text("current_timestamp()"))
    end_date = Column(UtcTimestamp)
    product_blocks = relationship(
        "ProductBlockTable",
        secondary=product_product_block_association,
        lazy="select",
        backref=backref("products", lazy=True),
        cascade_backrefs=False,
        passive_deletes=True,
    )
    workflows = relationship(
        "WorkflowTable",
        secondary=product_workflows_association,
        lazy="select",
        cascade_backrefs=False,
        passive_deletes=True,
    )
    fixed_inputs = relationship(
        "FixedInputTable", cascade="all, delete-orphan", backref=backref("product", lazy=True), passive_deletes=True
    )

    __table_args__ = {"extend_existing": True}

    def find_block_by_name(self, name: str) -> ProductBlockTable:
        return (
            object_session(self).query(ProductBlockTable).with_parent(self).filter(ProductBlockTable.name == name).one()
        )

    def fixed_input_value(self, name: str) -> str:
        return (
            object_session(self)
            .query(FixedInputTable)
            .with_parent(self)
            .filter(FixedInputTable.name == name)
            .value(FixedInputTable.value)
        )

    def _subscription_workflow_key(self, target: Target) -> Optional[str]:
        wfs = list(filter(lambda w: w.target == target, self.workflows))
        return wfs[0].name if len(wfs) > 0 else None

    def create_subscription_workflow_key(self) -> Optional[str]:
        return self._subscription_workflow_key(Target.CREATE)

    def terminate_subscription_workflow_key(self) -> Optional[str]:
        return self._subscription_workflow_key(Target.TERMINATE)

    def modify_subscription_workflow_key(self, name: str) -> Optional[str]:
        wfs = list(filter(lambda w: w.target == Target.MODIFY and w.name == name, self.workflows))
        return wfs[0].name if len(wfs) > 0 else None

    def workflow_by_key(self, name: str) -> Optional[WorkflowTable]:
        workflow = first_true(self.workflows, None, lambda wf: wf.name == name)
        return workflow


class FixedInputTable(BaseModel):
    __tablename__ = "fixed_inputs"

    fixed_input_id = Column(UUIDType, server_default=text("uuid_generate_v4()"), primary_key=True)
    name = Column(String(), nullable=False, unique=UniqueConstraint("name", "product_id"))
    value = Column(String(), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("current_timestamp()"))
    product_id = Column(
        UUIDType,
        ForeignKey("products.product_id", ondelete="CASCADE"),
        nullable=False,
        unique=UniqueConstraint("name", "product_id"),
    )

    __table_args__ = (UniqueConstraint("name", "product_id"), {"extend_existing": True})


class ProductBlockTable(BaseModel):
    __tablename__ = "product_blocks"
    product_block_id = Column(UUIDType, server_default=text("uuid_generate_v4()"), primary_key=True)
    name = Column(String(), nullable=False, unique=True)
    description = Column(Text(), nullable=False)
    tag = Column(String(TAG_LENGTH))
    status = Column(String(STATUS_LENGTH))
    created_at = Column(UtcTimestamp, nullable=False, server_default=text("current_timestamp()"))
    end_date = Column(UtcTimestamp)
    resource_types = relationship(
        "ResourceTypeTable",
        secondary=product_block_resource_type_association,
        lazy="select",
        backref=backref("product_blocks", lazy=True),
        cascade_backrefs=False,
        passive_deletes=True,
    )

    in_use_by_block_relations: list[ProductBlockRelationTable] = relationship(
        "ProductBlockRelationTable",
        lazy="subquery",
        cascade="all, delete-orphan",
        passive_deletes=True,
        backref=backref("depends_on", lazy=True),
        foreign_keys="[ProductBlockRelationTable.depends_on_id]",
    )

    depends_on_block_relations: list[ProductBlockRelationTable] = relationship(
        "ProductBlockRelationTable",
        lazy="subquery",
        cascade="all, delete-orphan",
        passive_deletes=True,
        backref=backref("in_use_by", lazy=True),
        foreign_keys="[ProductBlockRelationTable.in_use_by_id]",
    )

    in_use_by: list[ProductBlockTable] = association_proxy(
        "in_use_by_block_relations",
        "in_use_by",
        creator=lambda in_use_by: ProductBlockRelationTable(in_use_by=in_use_by),
    )

    depends_on: list[ProductBlockTable] = association_proxy(
        "depends_on_block_relations",
        "depends_on",
        creator=lambda depends_on: ProductBlockRelationTable(depends_on=depends_on),
    )

    @staticmethod
    def find_by_name(name: str) -> ProductBlockTable:
        return ProductBlockTable.query.filter(ProductBlockTable.name == name).one()

    @staticmethod
    def find_by_tag(tag: str) -> ProductBlockTable:
        return ProductBlockTable.query.filter(ProductBlockTable.tag == tag).one()

    def find_resource_type_by_name(self, name: str) -> ResourceTypeTable:
        return (
            object_session(self)
            .query(ResourceTypeTable)
            .with_parent(self)
            .filter(ResourceTypeTable.resource_type == name)
            .one()
        )


ProductBlockTable.parent_relations = ProductBlockTable.in_use_by_block_relations
ProductBlockTable.children_relations = ProductBlockTable.depends_on_block_relations


class ProductBlockRelationTable(BaseModel):
    __tablename__ = "product_block_relations"
    in_use_by_id = Column(UUIDType, ForeignKey("product_blocks.product_block_id", ondelete="CASCADE"), primary_key=True)

    depends_on_id = Column(
        UUIDType, ForeignKey("product_blocks.product_block_id", ondelete="CASCADE"), primary_key=True
    )

    min = Column(Integer())
    max = Column(Integer())


ProductBlockRelationTable.parent_id = ProductBlockRelationTable.in_use_by_id
ProductBlockRelationTable.child_id = ProductBlockRelationTable.depends_on_id

product_block_relation_index = Index(
    "product_block_relation_i_d_ix",
    ProductBlockRelationTable.in_use_by_id,
    ProductBlockRelationTable.depends_on_id,
    unique=True,
)


class ResourceTypeTable(BaseModel):
    __tablename__ = "resource_types"
    resource_type_id = Column(UUIDType, server_default=text("uuid_generate_v4()"), primary_key=True)
    resource_type = Column(String(510), nullable=False, unique=True)
    description = Column(Text())

    @staticmethod
    def find_by_resource_type(name: str) -> ResourceTypeTable:
        return ResourceTypeTable.query.filter(ResourceTypeTable.resource_type == name).one()


class WorkflowTable(BaseModel):
    __tablename__ = "workflows"
    workflow_id = Column(UUIDType, server_default=text("uuid_generate_v4()"), primary_key=True)
    name = Column(String(), nullable=False, unique=True)
    target = Column(String(), nullable=False)
    description = Column(Text(), nullable=True)
    created_at = Column(UtcTimestamp, nullable=False, server_default=text("current_timestamp()"))
    products = relationship(
        "ProductTable",
        secondary=product_workflows_association,
        lazy="select",
        passive_deletes=True,
        back_populates="workflows",
    )


class SubscriptionInstanceRelationTable(BaseModel):
    __tablename__ = "subscription_instance_relations"
    in_use_by_id = Column(
        UUIDType, ForeignKey("subscription_instances.subscription_instance_id", ondelete="CASCADE"), primary_key=True
    )

    depends_on_id = Column(
        UUIDType, ForeignKey("subscription_instances.subscription_instance_id", ondelete="CASCADE"), primary_key=True
    )

    order_id = Column(Integer(), primary_key=True)

    # Needed to make sure subscription instance is populated in the right domain model attribute, if more than one
    # attribute uses the same product block model.
    domain_model_attr = Column(Text())


SubscriptionInstanceRelationTable.parent_id = SubscriptionInstanceRelationTable.in_use_by_id
SubscriptionInstanceRelationTable.child_id = SubscriptionInstanceRelationTable.depends_on_id

subscription_relation_index = Index(
    "subscription_relation_i_d_o_ix",
    SubscriptionInstanceRelationTable.in_use_by_id,
    SubscriptionInstanceRelationTable.depends_on_id,
    SubscriptionInstanceRelationTable.order_id,
    unique=True,
)


class SubscriptionInstanceTable(BaseModel):
    __tablename__ = "subscription_instances"
    subscription_instance_id = Column(UUIDType, server_default=text("uuid_generate_v4()"), primary_key=True)
    subscription_id = Column(
        UUIDType, ForeignKey("subscriptions.subscription_id", ondelete="CASCADE"), nullable=False, index=True
    )
    subscription: SubscriptionTable  # From relation backref
    product_block_id = Column(UUIDType, ForeignKey("product_blocks.product_block_id"), nullable=False, index=True)
    product_block = relationship("ProductBlockTable", lazy="subquery")
    values = relationship(
        "SubscriptionInstanceValueTable",
        lazy="subquery",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="asc(SubscriptionInstanceValueTable.value)",
        backref=backref("subscription_instance", lazy=True),
    )
    label = Column(String(255))

    in_use_by_block_relations: list[SubscriptionInstanceRelationTable] = relationship(
        "SubscriptionInstanceRelationTable",
        lazy="subquery",
        cascade="all, delete-orphan",
        passive_deletes=True,
        backref=backref("depends_on", lazy=True),
        foreign_keys="[SubscriptionInstanceRelationTable.depends_on_id]",
    )

    depends_on_block_relations: list[SubscriptionInstanceRelationTable] = relationship(
        "SubscriptionInstanceRelationTable",
        lazy="subquery",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=SubscriptionInstanceRelationTable.order_id,
        collection_class=ordering_list("order_id"),
        backref=backref("in_use_by", lazy=True),
        foreign_keys="[SubscriptionInstanceRelationTable.in_use_by_id]",
    )

    in_use_by: list[SubscriptionInstanceTable] = association_proxy(
        "in_use_by_block_relations",
        "in_use_by",
        creator=lambda in_use_by: SubscriptionInstanceRelationTable(in_use_by=in_use_by),
    )

    depends_on: list[SubscriptionInstanceTable] = association_proxy(
        "depends_on_block_relations",
        "depends_on",
        creator=lambda depends_on: SubscriptionInstanceRelationTable(depends_on=depends_on),
    )

    def value_for_resource_type(self, name: Optional[str]) -> Optional[SubscriptionInstanceValueTable]:
        value = first_true(self.values, None, lambda x: x.resource_type.resource_type == name)
        return value


SubscriptionInstanceTable.parent_relations = SubscriptionInstanceTable.in_use_by_block_relations
SubscriptionInstanceTable.children_relations = SubscriptionInstanceTable.depends_on_block_relations


subscription_instance_s_pb_ix = Index(
    "subscription_instance_s_pb_ix",
    SubscriptionInstanceTable.subscription_instance_id,
    SubscriptionInstanceTable.subscription_id,
    SubscriptionInstanceTable.product_block_id,
)


class SubscriptionInstanceValueTable(BaseModel):
    __tablename__ = "subscription_instance_values"
    subscription_instance_value_id = Column(UUIDType, server_default=text("uuid_generate_v4()"), primary_key=True)
    subscription_instance_id = Column(
        UUIDType,
        ForeignKey("subscription_instances.subscription_instance_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_type_id = Column(UUIDType, ForeignKey("resource_types.resource_type_id"), nullable=False, index=True)
    resource_type = relationship("ResourceTypeTable", lazy="subquery")
    value = Column(Text(), nullable=False)


siv_si_rt_ix = Index(
    "siv_si_rt_ix",
    SubscriptionInstanceValueTable.subscription_instance_value_id,
    SubscriptionInstanceValueTable.subscription_instance_id,
    SubscriptionInstanceValueTable.resource_type_id,
)


class SubscriptionCustomerDescriptionTable(BaseModel):
    __tablename__ = "subscription_customer_descriptions"
    id = Column(UUIDType, server_default=text("uuid_generate_v4()"), primary_key=True)
    subscription_id = Column(
        UUIDType,
        ForeignKey("subscriptions.subscription_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=UniqueConstraint("customer_id", "subscription_id"),
    )
    subscription = relationship("SubscriptionTable")
    customer_id = Column(
        UUIDType, nullable=False, index=True, unique=UniqueConstraint("customer_id", "subscription_id")
    )
    description = Column(Text(), nullable=False)
    created_at = Column(UtcTimestamp, nullable=False, server_default=text("current_timestamp()"))

    __table_args__ = (
        UniqueConstraint("customer_id", "subscription_id", name="uniq_customer_subscription_description"),
    )


class SubscriptionTable(BaseModel):
    __tablename__ = "subscriptions"

    subscription_id = Column(UUIDType, server_default=text("uuid_generate_v4()"), primary_key=True)
    description = Column(Text(), nullable=False)
    status = Column(String(STATUS_LENGTH), nullable=False, index=True)
    product_id = Column(UUIDType, ForeignKey("products.product_id"), nullable=False, index=True)
    product = relationship("ProductTable")
    customer_id = Column(UUIDType, nullable=False, index=True)
    insync = Column(Boolean(), nullable=False)
    start_date = Column(UtcTimestamp, nullable=True)
    end_date = Column(UtcTimestamp)
    note = Column(Text())

    # `tsv` is a deferred column as we don't want or need it loaded every time we query a SubscriptionTable.
    # When updating stuff related to this see:
    # https://sqlalchemy-searchable.readthedocs.io/en/latest/alembic_migrations.html
    tsv = deferred(Column(TSVectorType))

    instances = relationship(
        "SubscriptionInstanceTable",
        lazy="select",
        bake_queries=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="asc(SubscriptionInstanceTable.subscription_instance_id)",
        foreign_keys="[SubscriptionInstanceTable.subscription_id]",
        backref=backref("subscription", lazy=True),
    )
    customer_descriptions = relationship(
        "SubscriptionCustomerDescriptionTable",
        lazy="select",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="subscription",
    )
    processes = relationship("ProcessSubscriptionTable", lazy=True, back_populates="subscription")

    @staticmethod
    def find_by_product_tag(tag: str) -> SearchQuery:
        return SubscriptionTable.query.join(ProductTable).filter(ProductTable.tag == tag)

    def find_instance_by_block_name(self, name: str) -> List[SubscriptionInstanceTable]:
        return [instance for instance in self.instances if instance.product_block.name == name]

    def find_values_for_resource_type(self, name: Optional[str]) -> List[SubscriptionInstanceValueTable]:
        return list(filter(None, (instance.value_for_resource_type(name) for instance in self.instances)))

    def product_blocks_with_values(self) -> List[Dict[str, List[Dict[str, str]]]]:
        return [
            {instance.product_block.name: [{v.resource_type.resource_type: v.value} for v in instance.values]}
            for instance in sorted(self.instances, key=lambda si: si.subscription_instance_id)
        ]


subscription_product_ix = Index(
    "subscription_product_ix", SubscriptionTable.subscription_id, SubscriptionTable.product_id
)
subscription_customer_ix = Index(
    "subscription_customer_ix", SubscriptionTable.subscription_id, SubscriptionTable.customer_id
)
subscription_tsv_ix = Index("subscription_tsv_ix", SubscriptionTable.tsv, postgresql_using="gin")


class EngineSettingsTable(BaseModel):
    __tablename__ = "engine_settings"
    global_lock = Column(Boolean(), default=False, nullable=False, primary_key=True)
    running_processes = Column(Integer(), default=0, nullable=False)
    __table_args__: tuple = (CheckConstraint(running_processes >= 0, name="check_running_processes_positive"), {})
