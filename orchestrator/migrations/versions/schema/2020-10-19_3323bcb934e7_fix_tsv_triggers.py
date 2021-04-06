"""Fix tsv triggers.

Revision ID: 3323bcb934e7
Revises: c112305b07d3
Create Date: 2020-12-10 09:22:46.491454

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "3323bcb934e7"
down_revision = "a76b9185b334"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        """
            DROP TRIGGER IF EXISTS subscriptions_upd_trigger ON subscriptions;

            CREATE OR REPLACE FUNCTION subscriptions_upd_trigger() RETURNS trigger
                LANGUAGE plpgsql
                AS $$
            BEGIN
                UPDATE subscriptions
                SET tsv = NULL
                WHERE subscription_id = NEW.subscription_id;
                RETURN NULL;
            END
            $$;

            CREATE TRIGGER subscriptions_upd_trigger
            AFTER UPDATE
            ON public.subscriptions
            FOR EACH ROW
                /*

                After updating a row on `subscriptions` we will perform another update on that same row to set the value of the
                `tsv` column. That has the potential to result in a cascade of triggers unless we specifically guard against it.

                This trigger will fire when anything but the tsv column changes and will set tsv to NULL.

                */
            WHEN (old.tsv IS NOT DISTINCT FROM new.tsv)
            EXECUTE FUNCTION public.subscriptions_upd_trigger();

            CREATE OR REPLACE FUNCTION subscriptions_set_tsv_trigger() RETURNS trigger
                LANGUAGE plpgsql
                AS $$
            BEGIN
                UPDATE subscriptions
                SET tsv = generate_subscription_tsv(NEW.subscription_id)
                WHERE subscription_id = NEW.subscription_id;
                RETURN NULL;
            END
            $$;

            CREATE TRIGGER subscriptions_set_tsv_trigger
            AFTER UPDATE
            ON public.subscriptions
            FOR EACH ROW
                /*

                After updating a row on `subscriptions` we will perform another update on that same row to set the value of the
                `tsv` column. That has the potential to result in a cascade of triggers unless we specifically guard against it.

                This trigger will only fire when tsv is set to NULL. This happens when something in another table or in this tables changes.
                Except for changes to the tsv column itself

                */
            WHEN (new.tsv IS NULL)
            EXECUTE FUNCTION public.subscriptions_set_tsv_trigger();
        """
    )


def downgrade() -> None:
    pass
