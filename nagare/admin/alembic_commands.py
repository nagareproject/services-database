# --
# Copyright (c) 2008-2020 Net-ng.
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
        return os.path.abspath(os.path.join(here, '..', 'templates'))


class AlembicBaseCommand(command.Command):
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
            print('FAILED: {}'.format(str(e)))
            return 1


class AlembicCommand(AlembicBaseCommand):

    def _set_arguments(self, parser):
        parser.add_argument('--db', help="name of the db section")
        super(AlembicCommand, self)._set_arguments(parser)

    def run(self, database_service, db=None, **params):
        directory = database_service.alembic_config['directory']
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
                'script_location': os.path.join(directory, db),
                'metadata': metadata,
                'engine': metadata.bind,
            },
            **params
        )


class Init(AlembicBaseCommand):
    DESC = 'initialize a new scripts directory'

    def run(self, database_service, services_service):
        directory = database_service.alembic_config['directory']

        if os.path.exists(directory):
            print("'{}' already exists".format(directory))
        else:
            os.mkdir(directory)

            for name in database_service.metadatas:
                try:
                    r = services_service(
                        super(Init, self).run,
                        directory=os.path.join(directory, name),
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
            help="don't emit SQL to database - dump to  standard output/file instead"
        )
        parser.add_argument(
            '--tag',
            help='arbitrary "tag" name. Can be used by custom env.py scripts'
        )
        parser.add_argument('revision')
        super(Stamp, self)._set_arguments(parser)


class Revision(AlembicCommand):
    DESC = 'create a new revision file'

    def _set_arguments(self, parser):
        parser.add_argument(
            '-m', '--message',
            help='message string to use with "revision"'
        )
        parser.add_argument(
            '-a', '--autogenerate', action='store_true',
            help='populate revision script with candidate migration operations,'
            'based on comparison of database to models'
        )
        parser.add_argument(
            '--sql', action='store_true',
            help="don't emit SQL to database - dump to  standard output/file instead"
        )
        parser.add_argument(
            '--head', default='head',
            help='specify head revision or <branchname>@head to base new revision on'
        )
        parser.add_argument(
            '--splice', action='store_true',
            help='allow a non-head revision as the "head" to splice onto'
        )
        parser.add_argument(
            '--branch-label',
            help='specify a branch label to apply to the  new revision'
        )
        parser.add_argument(
            '--version-path',
            help='specify specific path from config for version file'
        )
        parser.add_argument(
            '--rev-id',
            help='specify a hardcoded revision id instead of  generating one'
        )
        parser.add_argument(
            '--depends-on', action='append',
            help='specify one or more revision identifiers which this revision should depend on'
        )
        super(Revision, self)._set_arguments(parser)


class Upgrade(AlembicCommand):
    DESC = 'upgrade to a later version'

    def _set_arguments(self, parser):
        parser.add_argument(
            '--sql', action='store_true',
            help="don't emit SQL to database - dump to  standard output/file instead"
        )
        parser.add_argument(
            '--tag',
            help='arbitrary "tag" name. Can be used by custom env.py scripts'
        )
        parser.add_argument('revision')
        super(Upgrade, self)._set_arguments(parser)


class Downgrade(Upgrade):
    DESC = 'revert to a previous version'


class Current(AlembicCommand):
    DESC = 'display the current revision for a database'

    def _set_arguments(self, parser):
        parser.add_argument(
            '-v', '--verbose', action='store_true',
            help='use more verbose output'
        )
        super(Current, self)._set_arguments(parser)


class History(AlembicCommand):
    DESC = 'upgrade to a later version'

    def _set_arguments(self, parser):
        parser.add_argument(
            '-r', '--rev-range',
            help='specify a revision range; format is [start]:[end]")'
        )
        parser.add_argument(
            '-v', '--verbose', action='store_true',
            help='use more verbose output'
        )
        super(History, self)._set_arguments(parser)


class Branches(AlembicCommand):
    DESC = 'display the current revision for a database'

    def _set_arguments(self, parser):
        parser.add_argument(
            '-v', '--verbose', action='store_true',
            help='use more verbose output'
        )
        super(Branches, self)._set_arguments(parser)


class Heads(AlembicCommand):
    DESC = 'show current available heads in the script directory'

    def _set_arguments(self, parser):
        parser.add_argument(
            '-v', '--verbose', action='store_true',
            help='use more verbose output'
        )
        parser.add_argument(
            '--resolve-dependencies', action='store_true',
            help='treat dependency version as down revisions'
        )
        super(Heads, self)._set_arguments(parser)


class Merge(AlembicCommand):
    DESC = 'merge two revisions together and creates a new migration file'

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
            help='specify a hardcoded revision id instead of  generating one'
        )
        parser.add_argument(
            'revisions', nargs='+',
            help='one or more revisions, or "heads" for all heads'
        )
        super(Merge, self)._set_arguments(parser)


class Show(AlembicCommand):
    DESC = 'show the revision(s) denoted by the given symbol'

    def _set_arguments(self, parser):
        parser.add_argument(
            'rev',
            help='revision target'
        )
        super(Show, self)._set_arguments(parser)
