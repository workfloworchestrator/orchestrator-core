"""Add User and UserGroup products.

Revision ID: 45984f4b8010
Revises:
Create Date: 2022-11-11 15:50:39.611450

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "45984f4b8010"
down_revision = None
branch_labels = ("data",)
depends_on = "bed6bc0b197a"


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        """
INSERT INTO products (name, description, product_type, tag, status) VALUES ('User Group', 'user group administration', 'UserGroup', 'GROUP', 'active') RETURNING products.product_id
    """
    )
    conn.execute(
        """
INSERT INTO products (name, description, product_type, tag, status) VALUES ('User internal', 'user administration - internal', 'User', 'USER_INT', 'active') RETURNING products.product_id
    """
    )
    conn.execute(
        """
INSERT INTO products (name, description, product_type, tag, status) VALUES ('User external', 'user administration - external', 'User', 'USER_EXT', 'active') RETURNING products.product_id
    """
    )
    conn.execute(
        """
INSERT INTO fixed_inputs (name, value, product_id) VALUES ('affiliation', 'external', (SELECT products.product_id FROM products WHERE products.name IN ('User external'))), ('affiliation', 'internal', (SELECT products.product_id FROM products WHERE products.name IN ('User internal')))
    """
    )
    conn.execute(
        """
INSERT INTO product_blocks (name, description, tag, status) VALUES ('UserGroupBlock', 'user group block', 'USG', 'active') RETURNING product_blocks.product_block_id
    """
    )
    conn.execute(
        """
INSERT INTO product_blocks (name, description, tag, status) VALUES ('UserBlock', 'user block', 'US', 'active') RETURNING product_blocks.product_block_id
    """
    )
    conn.execute(
        """
INSERT INTO resource_types (resource_type, description) VALUES ('user_id', 'id of user') RETURNING resource_types.resource_type_id
    """
    )
    conn.execute(
        """
INSERT INTO resource_types (resource_type, description) VALUES ('age', 'age of user') RETURNING resource_types.resource_type_id
    """
    )
    conn.execute(
        """
INSERT INTO resource_types (resource_type, description) VALUES ('group_id', 'id of user group') RETURNING resource_types.resource_type_id
    """
    )
    conn.execute(
        """
INSERT INTO resource_types (resource_type, description) VALUES ('group_name', 'name of user group') RETURNING resource_types.resource_type_id
    """
    )
    conn.execute(
        """
INSERT INTO resource_types (resource_type, description) VALUES ('username', 'name of user') RETURNING resource_types.resource_type_id
    """
    )
    conn.execute(
        """
INSERT INTO product_product_blocks (product_id, product_block_id) VALUES ((SELECT products.product_id FROM products WHERE products.name IN ('User Group')), (SELECT product_blocks.product_block_id FROM product_blocks WHERE product_blocks.name IN ('UserGroupBlock')))
    """
    )
    conn.execute(
        """
INSERT INTO product_product_blocks (product_id, product_block_id) VALUES ((SELECT products.product_id FROM products WHERE products.name IN ('User external')), (SELECT product_blocks.product_block_id FROM product_blocks WHERE product_blocks.name IN ('UserBlock'))), ((SELECT products.product_id FROM products WHERE products.name IN ('User internal')), (SELECT product_blocks.product_block_id FROM product_blocks WHERE product_blocks.name IN ('UserBlock')))
    """
    )
    conn.execute(
        """
INSERT INTO product_block_relations (in_use_by_id, depends_on_id) VALUES ((SELECT product_blocks.product_block_id FROM product_blocks WHERE product_blocks.name IN ('UserBlock')), (SELECT product_blocks.product_block_id FROM product_blocks WHERE product_blocks.name IN ('UserGroupBlock')))
    """
    )
    conn.execute(
        """
INSERT INTO product_block_resource_types (product_block_id, resource_type_id) VALUES ((SELECT product_blocks.product_block_id FROM product_blocks WHERE product_blocks.name IN ('UserGroupBlock')), (SELECT resource_types.resource_type_id FROM resource_types WHERE resource_types.resource_type IN ('group_name')))
    """
    )
    conn.execute(
        """
INSERT INTO product_block_resource_types (product_block_id, resource_type_id) VALUES ((SELECT product_blocks.product_block_id FROM product_blocks WHERE product_blocks.name IN ('UserGroupBlock')), (SELECT resource_types.resource_type_id FROM resource_types WHERE resource_types.resource_type IN ('group_id')))
    """
    )
    conn.execute(
        """
INSERT INTO product_block_resource_types (product_block_id, resource_type_id) VALUES ((SELECT product_blocks.product_block_id FROM product_blocks WHERE product_blocks.name IN ('UserBlock')), (SELECT resource_types.resource_type_id FROM resource_types WHERE resource_types.resource_type IN ('username')))
    """
    )
    conn.execute(
        """
INSERT INTO product_block_resource_types (product_block_id, resource_type_id) VALUES ((SELECT product_blocks.product_block_id FROM product_blocks WHERE product_blocks.name IN ('UserBlock')), (SELECT resource_types.resource_type_id FROM resource_types WHERE resource_types.resource_type IN ('age')))
    """
    )
    conn.execute(
        """
INSERT INTO product_block_resource_types (product_block_id, resource_type_id) VALUES ((SELECT product_blocks.product_block_id FROM product_blocks WHERE product_blocks.name IN ('UserBlock')), (SELECT resource_types.resource_type_id FROM resource_types WHERE resource_types.resource_type IN ('user_id')))
    """
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        """
DELETE FROM product_block_resource_types WHERE product_block_resource_types.product_block_id IN (SELECT product_blocks.product_block_id FROM product_blocks WHERE product_blocks.name IN ('UserGroupBlock')) AND product_block_resource_types.resource_type_id = (SELECT resource_types.resource_type_id FROM resource_types WHERE resource_types.resource_type IN ('group_name'))
    """
    )
    conn.execute(
        """
DELETE FROM subscription_instance_values USING product_block_resource_types WHERE subscription_instance_values.subscription_instance_id IN (SELECT subscription_instances.subscription_instance_id FROM subscription_instances WHERE subscription_instances.subscription_instance_id IN (SELECT product_blocks.product_block_id FROM product_blocks WHERE product_blocks.name IN ('UserGroupBlock'))) AND product_block_resource_types.resource_type_id = (SELECT resource_types.resource_type_id FROM resource_types WHERE resource_types.resource_type IN ('group_name'))
    """
    )
    conn.execute(
        """
DELETE FROM product_block_resource_types WHERE product_block_resource_types.product_block_id IN (SELECT product_blocks.product_block_id FROM product_blocks WHERE product_blocks.name IN ('UserGroupBlock')) AND product_block_resource_types.resource_type_id = (SELECT resource_types.resource_type_id FROM resource_types WHERE resource_types.resource_type IN ('group_id'))
    """
    )
    conn.execute(
        """
DELETE FROM subscription_instance_values USING product_block_resource_types WHERE subscription_instance_values.subscription_instance_id IN (SELECT subscription_instances.subscription_instance_id FROM subscription_instances WHERE subscription_instances.subscription_instance_id IN (SELECT product_blocks.product_block_id FROM product_blocks WHERE product_blocks.name IN ('UserGroupBlock'))) AND product_block_resource_types.resource_type_id = (SELECT resource_types.resource_type_id FROM resource_types WHERE resource_types.resource_type IN ('group_id'))
    """
    )
    conn.execute(
        """
DELETE FROM product_block_resource_types WHERE product_block_resource_types.product_block_id IN (SELECT product_blocks.product_block_id FROM product_blocks WHERE product_blocks.name IN ('UserBlock')) AND product_block_resource_types.resource_type_id = (SELECT resource_types.resource_type_id FROM resource_types WHERE resource_types.resource_type IN ('username'))
    """
    )
    conn.execute(
        """
DELETE FROM subscription_instance_values USING product_block_resource_types WHERE subscription_instance_values.subscription_instance_id IN (SELECT subscription_instances.subscription_instance_id FROM subscription_instances WHERE subscription_instances.subscription_instance_id IN (SELECT product_blocks.product_block_id FROM product_blocks WHERE product_blocks.name IN ('UserBlock'))) AND product_block_resource_types.resource_type_id = (SELECT resource_types.resource_type_id FROM resource_types WHERE resource_types.resource_type IN ('username'))
    """
    )
    conn.execute(
        """
DELETE FROM product_block_resource_types WHERE product_block_resource_types.product_block_id IN (SELECT product_blocks.product_block_id FROM product_blocks WHERE product_blocks.name IN ('UserBlock')) AND product_block_resource_types.resource_type_id = (SELECT resource_types.resource_type_id FROM resource_types WHERE resource_types.resource_type IN ('age'))
    """
    )
    conn.execute(
        """
DELETE FROM subscription_instance_values USING product_block_resource_types WHERE subscription_instance_values.subscription_instance_id IN (SELECT subscription_instances.subscription_instance_id FROM subscription_instances WHERE subscription_instances.subscription_instance_id IN (SELECT product_blocks.product_block_id FROM product_blocks WHERE product_blocks.name IN ('UserBlock'))) AND product_block_resource_types.resource_type_id = (SELECT resource_types.resource_type_id FROM resource_types WHERE resource_types.resource_type IN ('age'))
    """
    )
    conn.execute(
        """
DELETE FROM product_block_resource_types WHERE product_block_resource_types.product_block_id IN (SELECT product_blocks.product_block_id FROM product_blocks WHERE product_blocks.name IN ('UserBlock')) AND product_block_resource_types.resource_type_id = (SELECT resource_types.resource_type_id FROM resource_types WHERE resource_types.resource_type IN ('user_id'))
    """
    )
    conn.execute(
        """
DELETE FROM subscription_instance_values USING product_block_resource_types WHERE subscription_instance_values.subscription_instance_id IN (SELECT subscription_instances.subscription_instance_id FROM subscription_instances WHERE subscription_instances.subscription_instance_id IN (SELECT product_blocks.product_block_id FROM product_blocks WHERE product_blocks.name IN ('UserBlock'))) AND product_block_resource_types.resource_type_id = (SELECT resource_types.resource_type_id FROM resource_types WHERE resource_types.resource_type IN ('user_id'))
    """
    )
    conn.execute(
        """
DELETE FROM subscription_instance_values WHERE subscription_instance_values.resource_type_id IN (SELECT resource_types.resource_type_id FROM resource_types WHERE resource_types.resource_type IN ('user_id', 'age', 'group_id', 'group_name', 'username'))
    """
    )
    conn.execute(
        """
DELETE FROM resource_types WHERE resource_types.resource_type IN ('user_id', 'age', 'group_id', 'group_name', 'username')
    """
    )
    conn.execute(
        """
DELETE FROM product_product_blocks WHERE product_product_blocks.product_id IN (SELECT products.product_id FROM products WHERE products.name IN ('User Group')) AND product_product_blocks.product_block_id IN (SELECT product_blocks.product_block_id FROM product_blocks WHERE product_blocks.name IN ('UserGroupBlock'))
    """
    )
    conn.execute(
        """
DELETE FROM product_product_blocks WHERE product_product_blocks.product_id IN (SELECT products.product_id FROM products WHERE products.name IN ('User external', 'User internal')) AND product_product_blocks.product_block_id IN (SELECT product_blocks.product_block_id FROM product_blocks WHERE product_blocks.name IN ('UserBlock'))
    """
    )
    conn.execute(
        """
DELETE FROM product_block_relations WHERE product_block_relations.in_use_by_id IN (SELECT product_blocks.product_block_id FROM product_blocks WHERE product_blocks.name IN ('UserBlock')) AND product_block_relations.depends_on_id IN (SELECT product_blocks.product_block_id FROM product_blocks WHERE product_blocks.name IN ('UserGroupBlock'))
    """
    )
    conn.execute(
        """
DELETE FROM fixed_inputs WHERE fixed_inputs.product_id IN (SELECT products.product_id FROM products WHERE products.name IN ('User external', 'User internal')) AND fixed_inputs.name = 'affiliation'
    """
    )
    conn.execute(
        """
DELETE FROM subscription_instances WHERE subscription_instances.product_block_id IN (SELECT product_blocks.product_block_id FROM product_blocks WHERE product_blocks.name IN ('UserGroupBlock', 'UserBlock'))
    """
    )
    conn.execute(
        """
DELETE FROM product_blocks WHERE product_blocks.name IN ('UserGroupBlock', 'UserBlock')
    """
    )
    conn.execute(
        """
DELETE FROM products WHERE products.name = 'User external'
    """
    )
    conn.execute(
        """
DELETE FROM products WHERE products.name = 'User Group'
    """
    )
    conn.execute(
        """
DELETE FROM products WHERE products.name = 'User internal'
    """
    )
