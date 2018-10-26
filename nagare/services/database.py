# --
# Copyright (c) 2008-2018 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --

import zope.sqlalchemy
from sqlalchemy import orm, MetaData, engine_from_config

from nagare.services import plugin
from nagare.server import reference
from alembic.migration import MigrationContext


session = orm.scoped_session(orm.sessionmaker())
metadata = MetaData()


def default_populate(app):
    pass


class Database(plugin.Plugin):
    CONFIG_SPEC = {
        '__many__': {  # Database sub-sections
            'activated': 'boolean(default=True)',
            'uri': 'string',  # Database connection string
            'debug': 'boolean(default=False)',  # Set the database engine in debug mode?

            'session': 'string(default="nagare.database:session")',
            'autoflush': 'boolean(default=True)',
            'autocommit': 'boolean(default=False)',
            'expire_on_commit': 'boolean(default=True)',
            'twophases': 'boolean(default=False)',

            'metadata': 'string(default="nagare.database:metadata")',  # Database metadata: database entities description
            'populate': 'string(default="nagare.services.database:default_populate")',
        },

        'upgrade': {
            'file_template': 'string(default=None)',
            'timezone': 'string(default=None)',
            'truncate_slug_length': 'integer(default=None)',
            'revision_environment': 'boolean(default=None)',
            'sourceless': 'boolean(default=None)',
            'version_locations': 'string(default=None)',
            'output_encoding': 'string(default=None)'
        }
    }

    def __init__(self, name, dist, upgrade, **configs):
        super(Database, self).__init__(name, dist)

        self.alembic_config = {k: v for k, v in upgrade.items() if v is not None}
        self.configs = configs

        self.metadatas = {}
        self.populates = []

    @staticmethod
    def _configure_session(session, autoflush, autocommit, expire_on_commit, twophases, **engine_config):
        session = reference.load_object(session)[0]
        session.configure(
            autoflush=autoflush, autocommit=autocommit,
            expire_on_commit=expire_on_commit,
            twophase=twophases
        )

        zope.sqlalchemy.register(session)

        return engine_config

    def _configure_engine(self, name, uri, debug, metadata, populate, **config):
        engine = engine_from_config(config, '', echo=debug, url=uri)

        metadata = reference.load_object(metadata)[0]
        metadata.bind = engine

        self.metadatas[name] = metadata

        return populate

    def handle_start(self, app):
        for name, config in self.configs.items():
            if config.pop('activated'):
                engine_config = self._configure_session(**config)
                populate = self._configure_engine(name, **engine_config)

                self.populates.append(reference.load_object(populate)[0])

        orm.configure_mappers()

    def create_all(self):
        for metadata in self.metadatas.values():
            metadata.create_all()

    def drop_all(self):
        for metadata in self.metadatas.values():
            engine = metadata.bind

            alembic = MigrationContext.configure(url=engine.url)
            alembic._version.drop(engine.connect(), checkfirst=True)

            metadata.drop_all()

    def populate_all(self, app):
        for populate in self.populates:
            populate(app)
