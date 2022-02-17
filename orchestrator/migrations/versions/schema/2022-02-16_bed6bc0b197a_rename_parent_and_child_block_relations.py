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
    # ### commands auto generated by Alembic - please adjust! ###/
    op.drop_index("subscription_relation_p_c_o_ix", table_name="subscription_instance_relations")
    op.create_index(
        "subscription_relation_p_c_o_ix",
        "subscription_instance_relations",
        ["parent_id", "child_id", "order_id"],
        unique=True,
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index("subscription_relation_p_c_o_ix", table_name="subscription_instance_relations")
    op.create_index(
        "subscription_relation_p_c_o_ix", "subscription_instance_relations", ["parent_id", "child_id"], unique=True
    )
    # ### end Alembic commands ###
