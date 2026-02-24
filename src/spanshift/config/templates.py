"""Default config and migration templates."""

TOML_TEMPLATE = """\
[spanshift]
migrations_dir = "migrations"
naming = "timestamp"

[environments.default]
project_id = "{project_id}"
instance_id = "{instance_id}"
database_id = "{database_id}"
"""

MIGRATION_TEMPLATE = '''\
"""{description}.

Revision: {revision}
Down-revision: {down_revision}
Created: {created}
"""

revision = "{revision}"
down_revision = {down_revision_repr}
description = "{description}"


def upgrade(ctx):
    ctx.execute_ddl([
        # Add your DDL statements here
    ])


def downgrade(ctx):
    ctx.execute_ddl([
        # Add your rollback DDL statements here
    ])
'''
