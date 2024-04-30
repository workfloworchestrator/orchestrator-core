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
    Select,
    String,
    Table,
    Text,
    TypeDecorator,
    UniqueConstraint,
    select,
    text,
)
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.engine import Dialect
from sqlalchemy.exc import DontWrapMixin
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.orderinglist import ordering_list
from sqlalchemy.orm import Mapped, backref, deferred, mapped_column, object_session, relationship
from sqlalchemy_utils import TSVectorType, UUIDType

from orchestrator.config.assignee import Assignee
from orchestrator.db.database import BaseModel, SearchQuery
from orchestrator.targets import Target
from orchestrator.utils.datetime import nowtz
from orchestrator.version import GIT_COMMIT_HASH

logger = structlog.get_logger(__name__)

TAG_LENGTH = 20
STATUS_LENGTH = 255


class UtcTimestampError(Exception, DontWrapMixin):
    pass


class UtcTimestamp(TypeDecorator):
    """Timestamps in UTC.

    This column type always returns timestamps with the UTC timezone, regardless of the database/connection time zone
    configuration. It also guards against accidentally trying to store Python naive timestamps (those without a time
    zone).
    """

    impl = sqlalchemy.types.TIMESTAMP(timezone=True)
    cache_ok = False
    python_type = datetime

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is not None:
            if value.tzinfo is None:
                raise UtcTimestampError(f"Expected timestamp with tzinfo. Got naive timestamp {value!r} instead")
        return value

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return value.astimezone(timezone.utc) if value else value


class ProcessTable(BaseModel):
    __tablename__ = "processes"

    process_id = mapped_column("pid", UUIDType, server_default=text("uuid_generate_v4()"), primary_key=True, index=True)
    workflow_id = mapped_column(
        "workflow_id", UUIDType, ForeignKey("workflows.workflow_id", ondelete="CASCADE"), nullable=False
    )
    assignee = mapped_column(String(50), server_default=Assignee.SYSTEM, nullable=False)
    last_status = mapped_column(String(50), nullable=False)
    last_step = mapped_column(String(255), nullable=True)
    started_at = mapped_column(UtcTimestamp, server_default=text("current_timestamp()"), nullable=False)
    last_modified_at = mapped_column(
        UtcTimestamp, server_default=text("current_timestamp()"), onupdate=nowtz, nullable=False
    )
    failed_reason = mapped_column(Text())
    traceback = mapped_column(Text())
    created_by = mapped_column(String(255), nullable=True)
    is_task = mapped_column(Boolean, nullable=False, server_default=text("false"), index=True)
    steps = relationship(
        "ProcessStepTable", cascade="delete", passive_deletes=True, order_by="asc(ProcessStepTable.executed_at)"
    )
    process_subscriptions = relationship("ProcessSubscriptionTable", lazy=True, passive_deletes=True)
    subscriptions = association_proxy("process_subscriptions", "subscription")

    workflow = relationship("WorkflowTable", back_populates="processes")

    @property
    def workflow_name(self) -> Column:
        return self.workflow.name


class ProcessStepTable(BaseModel):
    __tablename__ = "process_steps"

    step_id = mapped_column("stepid", UUIDType, server_default=text("uuid_generate_v4()"), primary_key=True)
    process_id = mapped_column(
        "pid", UUIDType, ForeignKey("processes.pid", ondelete="CASCADE"), nullable=False, index=True
    )
    name = mapped_column(String(), nullable=False)
    status = mapped_column(String(50), nullable=False)
    state = mapped_column(pg.JSONB(), nullable=False)  # type: ignore
    created_by = mapped_column(String(255), nullable=True)
    executed_at = mapped_column(UtcTimestamp, server_default=text("statement_timestamp()"), nullable=False)
    commit_hash = mapped_column(String(40), nullable=True, default=GIT_COMMIT_HASH)


class ProcessSubscriptionTable(BaseModel):
    __tablename__ = "processes_subscriptions"

    id = mapped_column(UUIDType, server_default=text("uuid_generate_v4()"), primary_key=True)
    process_id = mapped_column(
        "pid", UUIDType, ForeignKey("processes.pid", ondelete="CASCADE"), index=True, nullable=False
    )
    process = relationship("ProcessTable", back_populates="process_subscriptions")
    subscription_id = mapped_column(UUIDType, ForeignKey("subscriptions.subscription_id"), nullable=False, index=True)
    subscription = relationship("SubscriptionTable", lazy=True)
    created_at = mapped_column(UtcTimestamp, server_default=text("current_timestamp()"), nullable=False)
    workflow_target = mapped_column(String(255), nullable=False, server_default=Target.CREATE)


processes_subscriptions_ix = Index(
    "processes_subscriptions_ix", ProcessSubscriptionTable.process_id, ProcessSubscriptionTable.subscription_id
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
    __allow_unmapped__ = True

    product_id = mapped_column(UUIDType, server_default=text("uuid_generate_v4()"), primary_key=True)
    name = mapped_column(String(), nullable=False, unique=True)
    description = mapped_column(Text(), nullable=False)
    product_type = mapped_column(String(255), nullable=False)
    tag = mapped_column(String(TAG_LENGTH), nullable=False, index=True)
    status = mapped_column(String(STATUS_LENGTH), nullable=False)
    created_at = mapped_column(UtcTimestamp, nullable=False, server_default=text("current_timestamp()"))
    end_date = mapped_column(UtcTimestamp)
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
        secondaryjoin="and_(products_workflows.c.workflow_id == WorkflowTable.workflow_id, "
        "WorkflowTable.deleted_at == None)",
        lazy="select",
        cascade_backrefs=False,
        passive_deletes=True,
    )
    fixed_inputs = relationship(
        "FixedInputTable", cascade="all, delete-orphan", backref=backref("product", lazy=True), passive_deletes=True
    )

    __table_args__ = {"extend_existing": True}

    def find_block_by_name(self, name: str) -> ProductBlockTable:
        if session := object_session(self):
            return session.query(ProductBlockTable).with_parent(self).filter(ProductBlockTable.name == name).one()
        raise AssertionError("Session should not be None")

    def fixed_input_value(self, name: str) -> str:
        if session := object_session(self):
            return (
                session.query(FixedInputTable)
                .with_parent(self)
                .filter(FixedInputTable.name == name)
                .with_entities(FixedInputTable.value)
                .scalar()
            )
        raise AssertionError("Session should not be None")

    def _subscription_workflow_key(self, target: Target) -> str | None:
        wfs = list(filter(lambda w: w.target == target, self.workflows))
        return wfs[0].name if len(wfs) > 0 else None

    def create_subscription_workflow_key(self) -> str | None:
        return self._subscription_workflow_key(Target.CREATE)

    def terminate_subscription_workflow_key(self) -> str | None:
        return self._subscription_workflow_key(Target.TERMINATE)

    def modify_subscription_workflow_key(self, name: str) -> str | None:
        wfs = list(filter(lambda w: w.target == Target.MODIFY and w.name == name, self.workflows))
        return wfs[0].name if len(wfs) > 0 else None

    def workflow_by_key(self, name: str) -> WorkflowTable | None:
        return first_true(self.workflows, None, lambda wf: wf.name == name)  # type: ignore


class FixedInputTable(BaseModel):
    __tablename__ = "fixed_inputs"

    fixed_input_id = mapped_column(UUIDType, server_default=text("uuid_generate_v4()"), primary_key=True)
    name = mapped_column(String(), nullable=False)
    value = mapped_column(String(), nullable=False)
    created_at = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("current_timestamp()"))
    product_id = mapped_column(UUIDType, ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (UniqueConstraint("name", "product_id"), {"extend_existing": True})


class ProductBlockTable(BaseModel):
    __tablename__ = "product_blocks"

    __allow_unmapped__ = True

    product_block_id = mapped_column(UUIDType, server_default=text("uuid_generate_v4()"), primary_key=True)
    name = mapped_column(String(), nullable=False, unique=True)
    description = mapped_column(Text(), nullable=False)
    tag = mapped_column(String(TAG_LENGTH))
    status = mapped_column(String(STATUS_LENGTH))
    created_at = mapped_column(UtcTimestamp, nullable=False, server_default=text("current_timestamp()"))
    end_date = mapped_column(UtcTimestamp)
    resource_types = relationship(
        "ResourceTypeTable",
        secondary=product_block_resource_type_association,
        lazy="select",
        backref=backref("product_blocks", lazy=True),
        cascade_backrefs=False,
        passive_deletes=True,
    )

    in_use_by_block_relations: Mapped[list[ProductBlockRelationTable]] = relationship(
        "ProductBlockRelationTable",
        lazy="subquery",
        cascade="all, delete-orphan",
        passive_deletes=True,
        backref=backref("depends_on", lazy=True),
        foreign_keys="[ProductBlockRelationTable.depends_on_id]",
    )

    depends_on_block_relations: Mapped[list[ProductBlockRelationTable]] = relationship(
        "ProductBlockRelationTable",
        lazy="subquery",
        cascade="all, delete-orphan",
        passive_deletes=True,
        backref=backref("in_use_by", lazy=True),
        foreign_keys="[ProductBlockRelationTable.in_use_by_id]",
    )

    in_use_by = association_proxy(
        "in_use_by_block_relations",
        "in_use_by",
        creator=lambda in_use_by: ProductBlockRelationTable(in_use_by=in_use_by),
    )

    depends_on = association_proxy(
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
        if session := object_session(self):
            return (
                session.query(ResourceTypeTable).with_parent(self).filter(ResourceTypeTable.resource_type == name).one()
            )
        raise AssertionError("Session should not be None")


ProductBlockTable.parent_relations = ProductBlockTable.in_use_by_block_relations
ProductBlockTable.children_relations = ProductBlockTable.depends_on_block_relations


class ProductBlockRelationTable(BaseModel):
    __tablename__ = "product_block_relations"
    in_use_by_id = mapped_column(
        UUIDType, ForeignKey("product_blocks.product_block_id", ondelete="CASCADE"), primary_key=True
    )

    depends_on_id = mapped_column(
        UUIDType, ForeignKey("product_blocks.product_block_id", ondelete="CASCADE"), primary_key=True
    )

    min = mapped_column(Integer())
    max = mapped_column(Integer())


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
    resource_type_id = mapped_column(UUIDType, server_default=text("uuid_generate_v4()"), primary_key=True)
    resource_type = mapped_column(String(510), nullable=False, unique=True)
    description = mapped_column(Text())


class WorkflowTable(BaseModel):
    __tablename__ = "workflows"
    workflow_id = mapped_column(UUIDType, server_default=text("uuid_generate_v4()"), primary_key=True)
    name = mapped_column(String(), nullable=False, unique=True)
    target = mapped_column(String(), nullable=False)
    description = mapped_column(Text(), nullable=True)
    created_at = mapped_column(UtcTimestamp, nullable=False, server_default=text("current_timestamp()"))
    deleted_at = mapped_column(UtcTimestamp, deferred=True)

    products = relationship(
        "ProductTable",
        secondary=product_workflows_association,
        lazy="select",
        passive_deletes=True,
        back_populates="workflows",
    )
    processes = relationship("ProcessTable", lazy="select", cascade="all, delete-orphan", back_populates="workflow")

    @staticmethod
    def select() -> Select:
        return select(WorkflowTable).filter(WorkflowTable.deleted_at.is_(None))

    def delete(self) -> WorkflowTable:
        self.deleted_at = nowtz()
        return self


class SubscriptionInstanceRelationTable(BaseModel):
    __tablename__ = "subscription_instance_relations"
    in_use_by_id = mapped_column(
        UUIDType, ForeignKey("subscription_instances.subscription_instance_id", ondelete="CASCADE"), primary_key=True
    )

    depends_on_id = mapped_column(
        UUIDType, ForeignKey("subscription_instances.subscription_instance_id", ondelete="CASCADE"), primary_key=True
    )

    order_id = mapped_column(Integer(), primary_key=True)

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
    __allow_unmapped__ = True

    subscription_instance_id = mapped_column(UUIDType, server_default=text("uuid_generate_v4()"), primary_key=True)
    subscription_id = mapped_column(
        UUIDType, ForeignKey("subscriptions.subscription_id", ondelete="CASCADE"), nullable=False, index=True
    )
    subscription: SubscriptionTable  # From relation backref
    product_block_id = mapped_column(
        UUIDType, ForeignKey("product_blocks.product_block_id"), nullable=False, index=True
    )
    product_block = relationship("ProductBlockTable", lazy="subquery")
    values = relationship(
        "SubscriptionInstanceValueTable",
        lazy="subquery",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="asc(SubscriptionInstanceValueTable.value)",
        backref=backref("subscription_instance", lazy=True),
    )
    label = mapped_column(String(255))

    in_use_by_block_relations: Mapped[list[SubscriptionInstanceRelationTable]] = relationship(
        "SubscriptionInstanceRelationTable",
        lazy="subquery",
        cascade="all, delete-orphan",
        passive_deletes=True,
        backref=backref("depends_on", lazy=True),
        foreign_keys="[SubscriptionInstanceRelationTable.depends_on_id]",
    )

    depends_on_block_relations: Mapped[list[SubscriptionInstanceRelationTable]] = relationship(
        "SubscriptionInstanceRelationTable",
        lazy="subquery",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=SubscriptionInstanceRelationTable.order_id,
        collection_class=ordering_list("order_id"),
        backref=backref("in_use_by", lazy=True),
        foreign_keys="[SubscriptionInstanceRelationTable.in_use_by_id]",
    )

    in_use_by = association_proxy(
        "in_use_by_block_relations",
        "in_use_by",
        creator=lambda in_use_by: SubscriptionInstanceRelationTable(in_use_by=in_use_by),
    )

    depends_on = association_proxy(
        "depends_on_block_relations",
        "depends_on",
        creator=lambda depends_on: SubscriptionInstanceRelationTable(depends_on=depends_on),
    )

    def value_for_resource_type(self, name: str | None) -> SubscriptionInstanceValueTable | None:
        return first_true(self.values, None, lambda x: x.resource_type.resource_type == name)  # type: ignore


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
    subscription_instance_value_id = mapped_column(
        UUIDType, server_default=text("uuid_generate_v4()"), primary_key=True
    )
    subscription_instance_id = mapped_column(
        UUIDType,
        ForeignKey("subscription_instances.subscription_instance_id", ondelete="CASCADE"),
        index=True,
    )
    resource_type_id = mapped_column(
        UUIDType, ForeignKey("resource_types.resource_type_id"), nullable=False, index=True
    )
    resource_type = relationship("ResourceTypeTable", lazy="subquery")
    value = mapped_column(Text(), nullable=False)


siv_si_rt_ix = Index(
    "siv_si_rt_ix",
    SubscriptionInstanceValueTable.subscription_instance_value_id,
    SubscriptionInstanceValueTable.subscription_instance_id,
    SubscriptionInstanceValueTable.resource_type_id,
)


class SubscriptionCustomerDescriptionTable(BaseModel):
    __tablename__ = "subscription_customer_descriptions"
    id = mapped_column(UUIDType, server_default=text("uuid_generate_v4()"), primary_key=True)
    subscription_id = mapped_column(
        UUIDType,
        ForeignKey("subscriptions.subscription_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subscription = relationship("SubscriptionTable")
    customer_id = mapped_column(String, nullable=False, index=True)
    description = mapped_column(Text(), nullable=False)
    created_at = mapped_column(UtcTimestamp, nullable=False, server_default=text("current_timestamp()"))

    __table_args__ = (
        UniqueConstraint("customer_id", "subscription_id", name="uniq_customer_subscription_description"),
    )


class SubscriptionTable(BaseModel):
    __tablename__ = "subscriptions"

    subscription_id = mapped_column(
        UUIDType, server_default=text("uuid_generate_v4()"), primary_key=True, nullable=False
    )
    description = mapped_column(Text(), nullable=False)
    status = mapped_column(String(STATUS_LENGTH), nullable=False, index=True)
    product_id = mapped_column(UUIDType, ForeignKey("products.product_id"), nullable=False, index=True)
    product = relationship("ProductTable")
    customer_id = mapped_column(String, index=True, nullable=False)
    insync = mapped_column(Boolean())
    start_date = mapped_column(UtcTimestamp, nullable=True)
    end_date = mapped_column(UtcTimestamp)
    note = mapped_column(Text())

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

    def find_instance_by_block_name(self, name: str) -> list[SubscriptionInstanceTable]:
        return [instance for instance in self.instances if instance.product_block.name == name]

    def find_values_for_resource_type(self, name: str | None) -> list[SubscriptionInstanceValueTable]:
        return list(filter(None, (instance.value_for_resource_type(name) for instance in self.instances)))

    def product_blocks_with_values(self) -> list[dict[str, list[dict[str, str]]]]:
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


class SubscriptionMetadataTable(BaseModel):
    __tablename__ = "subscription_metadata"
    subscription_id = mapped_column(
        UUIDType,
        ForeignKey("subscriptions.subscription_id", ondelete="CASCADE"),
        primary_key=True,
    )
    metadata_ = mapped_column("metadata", pg.JSONB(), nullable=False)  # type: ignore

    @staticmethod
    def find_by_subscription_id(subscription_id: str) -> SubscriptionMetadataTable | None:
        return SubscriptionMetadataTable.query.get(subscription_id)


class SubscriptionSearchView(BaseModel):
    __tablename__ = "subscriptions_search"
    subscription_id = mapped_column(
        UUIDType, ForeignKey("subscriptions.subscription_id"), nullable=False, index=True, primary_key=True
    )

    tsv = deferred(mapped_column(TSVectorType))

    subscription = relationship("SubscriptionTable", foreign_keys=[subscription_id])


class EngineSettingsTable(BaseModel):
    __tablename__ = "engine_settings"
    global_lock = mapped_column(Boolean(), default=False, nullable=False, primary_key=True)
    running_processes = mapped_column(Integer(), default=0, nullable=False)
    __table_args__: tuple = (CheckConstraint(running_processes >= 0, name="check_running_processes_positive"), {})
