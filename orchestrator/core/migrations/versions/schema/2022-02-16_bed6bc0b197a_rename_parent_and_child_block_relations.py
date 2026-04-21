"""rename_parent_and_child_block_relations.

Revision ID: bed6bc0b197a
Revises: 19cdd3ab86f6
Create Date: 2022-02-16 14:20:19.813435

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "bed6bc0b197a"
down_revision = "19cdd3ab86f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("product_block_relation_p_c_ix", table_name="product_block_relations")
    op.drop_constraint("product_block_relations_parent_id_fkey", "product_block_relations", type_="foreignkey")
    op.drop_constraint("product_block_relations_child_id_fkey", "product_block_relations", type_="foreignkey")
    op.alter_column("product_block_relations", "parent_id", new_column_name="in_use_by_id")
    op.alter_column("product_block_relations", "child_id", new_column_name="depends_on_id")
    op.create_index(
        "product_block_relation_i_d_ix", "product_block_relations", ["in_use_by_id", "depends_on_id"], unique=True
    )
    op.create_foreign_key(
        "product_block_relations_in_use_by_id_fkey",
        "product_block_relations",
        "product_blocks",
        ["in_use_by_id"],
        ["product_block_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "product_block_relations_depends_on_id_fkey",
        "product_block_relations",
        "product_blocks",
        ["depends_on_id"],
        ["product_block_id"],
        ondelete="CASCADE",
    )

    op.drop_index("subscription_relation_p_c_o_ix", table_name="subscription_instance_relations")
    op.drop_constraint(
        "subscription_instance_relations_parent_id_fkey", "subscription_instance_relations", type_="foreignkey"
    )
    op.drop_constraint(
        "subscription_instance_relations_child_id_fkey", "subscription_instance_relations", type_="foreignkey"
    )
    op.alter_column("subscription_instance_relations", "parent_id", new_column_name="in_use_by_id")
    op.alter_column("subscription_instance_relations", "child_id", new_column_name="depends_on_id")
    op.create_index(
        "subscription_relation_i_d_o_ix",
        "subscription_instance_relations",
        ["in_use_by_id", "depends_on_id", "order_id"],
        unique=True,
    )
    op.create_foreign_key(
        "subscription_instance_relations_in_use_by_id_fkey",
        "subscription_instance_relations",
        "subscription_instances",
        ["in_use_by_id"],
        ["subscription_instance_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "subscription_instance_relations_depends_on_id_fkey",
        "subscription_instance_relations",
        "subscription_instances",
        ["depends_on_id"],
        ["subscription_instance_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_index("product_block_relation_i_d_ix", table_name="product_block_relations")
    op.drop_constraint("product_block_relations_in_use_by_id_fkey", "product_block_relations", type_="foreignkey")
    op.drop_constraint("product_block_relations_depends_on_id_fkey", "product_block_relations", type_="foreignkey")
    op.alter_column("product_block_relations", "in_use_by_id", new_column_name="parent_id")
    op.alter_column("product_block_relations", "depends_on_id", new_column_name="child_id")
    op.create_index("product_block_relation_p_c_ix", "product_block_relations", ["parent_id", "child_id"], unique=True)
    op.create_foreign_key(
        "product_block_relations_parent_id_fkey",
        "product_block_relations",
        "product_blocks",
        ["parent_id"],
        ["product_block_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "product_block_relations_child_id_fkey",
        "product_block_relations",
        "product_blocks",
        ["child_id"],
        ["product_block_id"],
        ondelete="CASCADE",
    )

    op.drop_index("subscription_relation_i_d_o_ix", table_name="subscription_instance_relations")
    op.drop_constraint(
        "subscription_instance_relations_in_use_by_id_fkey", "subscription_instance_relations", type_="foreignkey"
    )
    op.drop_constraint(
        "subscription_instance_relations_depends_on_id_fkey", "subscription_instance_relations", type_="foreignkey"
    )
    op.alter_column("subscription_instance_relations", "in_use_by_id", new_column_name="parent_id")
    op.alter_column("subscription_instance_relations", "depends_on_id", new_column_name="child_id")
    op.create_index(
        "subscription_relation_p_c_o_ix",
        "subscription_instance_relations",
        ["parent_id", "child_id", "order_id"],
        unique=True,
    )
    op.create_foreign_key(
        "subscription_instance_relations_parent_id_fkey",
        "subscription_instance_relations",
        "subscription_instances",
        ["parent_id"],
        ["subscription_instance_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "subscription_instance_relations_child_id_fkey",
        "subscription_instance_relations",
        "subscription_instances",
        ["child_id"],
        ["subscription_instance_id"],
        ondelete="CASCADE",
    )
