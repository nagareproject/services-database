# --
# Copyright (c) 2008-2025 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --

import os

try:
    from ConfigParser import RawConfigParser
except ImportError:
    from configparser import RawConfigParser


from alembic import config as alembic_config
from alembic import command as alembic_command
from alembic import migration

from nagare import commands
from nagare.admin import command


class CMDOpts:
    quiet = True


class AlembicConfig(alembic_config.Config):
    def __init__(self, dist_location, quiet, **config):
        super(AlembicConfig, self).__init__(
            os.path.join(config['script_location'], '__init__.py'), cmd_opts=CMDOpts if quiet else None
        )

        self.dist_location = dist_location

        self.file_config = RawConfigParser()
        for k, v in config.items():
            self.set_main_option(k, v)

    @classmethod
    def create(cls, db, quiet, database_service, config):
        config = dict(database_service.alembic_config, **config)
        return cls(
            database_service.location, quiet, script_location=os.path.join(config.pop('directory'), db), **config
        )

    def get_template_directory(self):
        return os.path.abspath(os.path.join(self.dist_location, 'nagare', 'templates'))


def get_heads(db, database_service, **config):
    alembic_config = AlembicConfig.create(db, False, database_service, config)
    script_location = alembic_config.get_main_option('script_location')

    return (
        alembic_command.ScriptDirectory.from_config(alembic_config).get_heads()
        if os.access(script_location, os.F_OK)
        else None
    )


def get_current_revision(engine):
    with engine.connect() as connection:
        migration_context = migration.MigrationContext.configure(connection)
        return migration_context.get_current_revision()


def drop_version(engine):
    with engine.connect() as connection:
        alembic = migration.MigrationContext.configure(connection)
        alembic._version.drop(connection, checkfirst=True)


class AlembicBaseCommand(command.Command):
    WITH_STARTED_SERVICES = True

    def set_arguments(self, parser):
        parser.add_argument('--db', help='name of the db section')
        super(AlembicBaseCommand, self).set_arguments(parser)

    def run(self, db, quiet, config, database_service, **params):
        alembic_config = AlembicConfig.create(db, quiet, database_service, config)

        getattr(alembic_command, self.__class__.__name__.lower())(alembic_config, **params)


class AlembicCommand(AlembicBaseCommand):
    def run(self, db, database_service, services_service, **params):
        metadatas = {metadata.name: metadata for metadata in database_service.metadatas}

        if not db:
            if len(metadatas) == 1:
                db = next(iter(metadatas))
            else:
                raise commands.ArgumentError('missing --db option')

        metadata = metadatas[db]

        return super(AlembicCommand, self).run(
            db,
            False,
            {
                'db': db,
                'metadata': metadata,
                'engine': database_service.get_engine(metadata),
                'services': services_service,
            },
            database_service,
            **params,
        )


class Init(AlembicBaseCommand):
    DESC = 'initialize a new scripts directory'

    def run(self, db, database_service, services_service):
        for metadata in database_service.metadatas:
            if (db is None) or (metadata.name == db):
                directory = os.path.join(database_service.alembic_config['directory'], metadata.name)

                if os.path.exists(directory):
                    print("*** '{}' already exists".format(directory))
                else:
                    os.makedirs(directory)

                    try:
                        r = services_service(
                            super(Init, self).run,
                            metadata.name,
                            True,
                            {},
                            directory=directory,
                            template='alembic_nagare',
                        )
                        if r:
                            return r
                    except UnboundLocalError as e:
                        if 'config_file' not in e.args[0]:
                            raise

        return 0


class Stamp(AlembicCommand):
    DESC = '"stamp" the revision table with the given revision; don\'t run any migrations'

    def set_arguments(self, parser):
        parser.add_argument(
            '--sql', action='store_true', help="don't emit SQL to database - dump to  standard output/file instead"
        )
        parser.add_argument('--tag', help='arbitrary "tag" name. Can be used by custom env.py scripts')
        parser.add_argument('revision')
        super(Stamp, self).set_arguments(parser)


class Revision(AlembicCommand):
    DESC = 'create a new revision file'

    def set_arguments(self, parser):
        parser.add_argument('-m', '--message', help='message string to use with "revision"')
        parser.add_argument(
            '-a',
            '--autogenerate',
            action='store_true',
            help='populate revision script with candidate migration operations,'
            'based on comparison of database to models',
        )
        parser.add_argument(
            '--sql', action='store_true', help="don't emit SQL to database - dump to  standard output/file instead"
        )
        parser.add_argument(
            '--head', default='head', help='specify head revision or <branchname>@head to base new revision on'
        )
        parser.add_argument(
            '--splice', action='store_true', help='allow a non-head revision as the "head" to splice onto'
        )
        parser.add_argument('--branch-label', help='specify a branch label to apply to the  new revision')
        parser.add_argument('--version-path', help='specify specific path from config for version file')
        parser.add_argument('--rev-id', help='specify a hardcoded revision id instead of  generating one')
        parser.add_argument(
            '--depends-on',
            action='append',
            help='specify one or more revision identifiers which this revision should depend on',
        )
        super(Revision, self).set_arguments(parser)


class Upgrade(AlembicCommand):
    DESC = 'upgrade to a later version'

    def set_arguments(self, parser):
        parser.add_argument(
            '--sql', action='store_true', help="don't emit SQL to database - dump to  standard output/file instead"
        )
        parser.add_argument('--tag', help='arbitrary "tag" name. Can be used by custom env.py scripts')
        parser.add_argument('revision')
        super(Upgrade, self).set_arguments(parser)


class Downgrade(Upgrade):
    DESC = 'revert to a previous version'


class Current(AlembicCommand):
    DESC = 'show the current revision for a database'

    def set_arguments(self, parser):
        parser.add_argument('-v', '--verbose', action='store_true', help='use more verbose output')
        super(Current, self).set_arguments(parser)


class History(AlembicCommand):
    DESC = 'list changeset scripts in chronological order'

    def set_arguments(self, parser):
        parser.add_argument('-r', '--rev-range', help='specify a revision range; format is [start]:[end]")')
        parser.add_argument('-v', '--verbose', action='store_true', help='use more verbose output')
        super(History, self).set_arguments(parser)


class Branches(AlembicCommand):
    DESC = 'show current branch points'

    def set_arguments(self, parser):
        parser.add_argument('-v', '--verbose', action='store_true', help='use more verbose output')
        super(Branches, self).set_arguments(parser)


class Heads(AlembicCommand):
    DESC = 'show current available heads in the script directory'

    def set_arguments(self, parser):
        parser.add_argument('-v', '--verbose', action='store_true', help='use more verbose output')
        parser.add_argument(
            '--resolve-dependencies', action='store_true', help='treat dependency version as down revisions'
        )
        super(Heads, self).set_arguments(parser)


class Merge(AlembicCommand):
    DESC = 'merge two revisions together and creates a new migration file'

    def set_arguments(self, parser):
        parser.add_argument('-m', '--message', help='message string to use with "revision"')
        parser.add_argument('--branch-label', help='label name to apply to the new revision')
        parser.add_argument('--rev-id', help='specify a hardcoded revision id instead of  generating one')
        parser.add_argument('revisions', nargs='+', help='one or more revisions, or "heads" for all heads')
        super(Merge, self).set_arguments(parser)


class Show(AlembicCommand):
    DESC = 'show the revision(s) denoted by the given symbol'

    def set_arguments(self, parser):
        parser.add_argument('rev', help='revision target')
        super(Show, self).set_arguments(parser)
