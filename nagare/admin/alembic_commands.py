# --
# Copyright (c) 2008-2018 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --

import os
from ConfigParser import RawConfigParser

from nagare.admin import command
from alembic import config, util, command as alembic_command


class Config(config.Config):
    def __init__(self, **config):
        super(Config, self).__init__()

        self.file_config = RawConfigParser()
        for k, v in config.items():
            self.set_main_option(k, v)

    def get_template_directory(self):
        here = os.path.abspath(os.path.dirname(__file__))
        return os.path.join(here, '..', 'templates')


class AlembicBaseCommand(command.Command):
    ROOT = 'database_versions'
    WITH_STARTED_SERVICES = True

    def _set_arguments(self, parser):
        pass

    def set_arguments(self, parser):
        self._set_arguments(parser)
        super(AlembicBaseCommand, self).set_arguments(parser)

    def run(self, database_service, config=None, **params):
        cfg = Config(**dict(config or {}, **database_service.alembic_config))

        try:
            getattr(alembic_command, self.__class__.__name__.lower())(cfg, **params)
            return 0
        except util.exc.CommandError as e:
            print 'FAILED:', str(e)
            return 1


class AlembicCommand(AlembicBaseCommand):

    def _set_arguments(self, parser):
        parser.add_argument('--db', help="Name of the db section")
        super(AlembicCommand, self)._set_arguments(parser)

    def run(self, database_service, db=None, **params):
        metadatas = database_service.metadatas

        if not db:
            if len(metadatas) == 1:
                db = next(iter(metadatas))
            else:
                raise command.ArgumentError('missing --db option')

        metadata = metadatas[db]

        return super(AlembicCommand, self).run(
            database_service,
            {
                'script_location': os.path.join(self.ROOT, db),
                'metadata': metadata,
                'engine': metadata.bind,
            },
            **params
        )


class Init(AlembicBaseCommand):
    DESC = 'Initialize a new scripts directory'

    def run(self, database_service, services_service):
        os.mkdir(self.ROOT)

        for name in database_service.metadatas:
            try:
                r = services_service(
                    super(Init, self).run,
                    directory=os.path.join(self.ROOT, name),
                    template='alembic_nagare'
                )
                if r:
                    return r
            except UnboundLocalError as e:
                if 'config_file' not in e.args[0]:
                    raise

        return 0


class Stamp(AlembicCommand):
    DESC = '"stamp" the revision table with the given revision; don\'t run any migrations'

    def _set_arguments(self, parser):
        parser.add_argument(
            '--sql', action='store_true',
            help="Don't emit SQL to database - dump to  standard output/file instead"
        )
        parser.add_argument(
            '--tag',
            help='Arbitrary "tag" name. Can be used by custom env.py scripts'
        )
        parser.add_argument('revision')
        super(Stamp, self)._set_arguments(parser)


class Revision(AlembicCommand):
    DESC = 'Create a new revision file'

    def _set_arguments(self, parser):
        parser.add_argument(
            '-m', '--message',
            help='Message string to use with "revision"'
        )
        parser.add_argument(
            '-a', '--autogenerate', action='store_true',
            help='Populate revision script with candidate migration operations,'
            'based on comparison of database to models'
        )
        parser.add_argument(
            '--sql', action='store_true',
            help="Don't emit SQL to database - dump to  standard output/file instead"
        )
        parser.add_argument(
            '--head', default='head',
            help='Specify head revision or <branchname>@head to base new revision on'
        )
        parser.add_argument(
            '--splice', action='store_true',
            help='Allow a non-head revision as the "head" to splice onto'
        )
        parser.add_argument(
            '--branch-label',
            help='Specify a branch label to apply to the  new revision'
        )
        parser.add_argument(
            '--version-path',
            help='Specify specific path from config for version file'
        )
        parser.add_argument(
            '--rev-id',
            help='Specify a hardcoded revision id instead of  generating one'
        )
        parser.add_argument(
            '--depends-on', action='append',
            help='Specify one or more revision identifiers which this revision should depend on'
        )
        super(Revision, self)._set_arguments(parser)


class Upgrade(AlembicCommand):
    DESC = 'Upgrade to a later version'

    def _set_arguments(self, parser):
        parser.add_argument(
            '--sql', action='store_true',
            help="Don't emit SQL to database - dump to  standard output/file instead"
        )
        parser.add_argument(
            '--tag',
            help='Arbitrary "tag" name. Can be used by custom env.py scripts'
        )
        parser.add_argument('revision')
        super(Upgrade, self)._set_arguments(parser)


class Downgrade(Upgrade):
    DESC = 'Revert to a previous version'


class Current(AlembicCommand):
    DESC = 'Display the current revision for a database'

    def _set_arguments(self, parser):
        parser.add_argument(
            '-v', '--verbose', action='store_true',
            help='Use more verbose output'
        )
        super(Current, self)._set_arguments(parser)


class History(AlembicCommand):
    DESC = 'Upgrade to a later version'

    def _set_arguments(self, parser):
        parser.add_argument(
            '-r', '--rev-range',
            help='Specify a revision range; format is [start]:[end]")'
        )
        parser.add_argument(
            '-v', '--verbose', action='store_true',
            help='Use more verbose output'
        )
        super(History, self)._set_arguments(parser)


class Branches(AlembicCommand):
    DESC = 'Display the current revision for a database'

    def _set_arguments(self, parser):
        parser.add_argument(
            '-v', '--verbose', action='store_true',
            help='Use more verbose output'
        )
        super(Branches, self)._set_arguments(parser)


class Heads(AlembicCommand):
    DESC = 'Show current available heads in the script directory'

    def _set_arguments(self, parser):
        parser.add_argument(
            '-v', '--verbose', action='store_true',
            help='Use more verbose output'
        )
        parser.add_argument(
            '--resolve-dependencies', action='store_true',
            help='treat dependency version as down revisions'
        )
        super(Heads, self)._set_arguments(parser)


class Merge(AlembicCommand):
    DESC = 'Merge two revisions together.  Creates a new migration file'

    def _set_arguments(self, parser):
        parser.add_argument(
            '-m', '--message',
            help='message string to use with "revision"'
        )
        parser.add_argument(
            '--branch-label',
            help='label name to apply to the new revision'
        )
        parser.add_argument(
            '--rev-id',
            help='Specify a hardcoded revision id instead of  generating one'
        )
        parser.add_argument(
            'revisions', nargs='+',
            help='one or more revisions, or "heads" for all heads'
        )
        super(Merge, self)._set_arguments(parser)


class Show(AlembicCommand):
    DESC = 'Show the revision(s) denoted by the given symbol'

    def _set_arguments(self, parser):
        parser.add_argument(
            'rev',
            help='revision target'
        )
        super(Show, self)._set_arguments(parser)
