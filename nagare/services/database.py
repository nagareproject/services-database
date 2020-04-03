# --
# Copyright (c) 2008-2020 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --

import zope.sqlalchemy
from sqlalchemy import orm, event, MetaData, engine_from_config

from nagare.services import plugin
from nagare.server import reference
from alembic.migration import MigrationContext


session = orm.scoped_session(orm.sessionmaker())
metadata = MetaData()


class FKRelationshipBase(object):
    pass


def default_populate(app):
    pass


def configure_mappers(collections_class=set):
    @event.listens_for(orm.mapper, 'mapper_configured')
    def config(mapper, cls):
        for key, value in list(cls.__dict__.items()):
            if isinstance(value, FKRelationshipBase):
                value.config(cls, key, collections_class)

    orm.configure_mappers()


class Database(plugin.Plugin):
    CONFIG_SPEC = {
        'collections_class': 'string(default=set)',

        '__many__': {  # Database sub-sections
            'activated': 'boolean(default=True)',
            'uri': 'string(default=None)',  # Database connection string
            'debug': 'boolean(default=False)',  # Set the database engine in debug mode?

            'session': 'string(default="nagare.database:session")',
            'autoflush': 'boolean(default=True)',
            'autocommit': 'boolean(default=False)',
            'expire_on_commit': 'boolean(default=True)',
            'twophases': 'boolean(default=False)',

            'metadata': 'string(default="nagare.database:metadata")',  # Database metadata: database entities description
            'populate': 'string(default="nagare.services.database:default_populate")'
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

    def __init__(self, name, dist, collections_class, upgrade, **configs):
        super(Database, self).__init__(
            name, dist,
            collections_class=collections_class, upgrade=upgrade,
            **configs)

        self.collections_class = reference.load_object(collections_class)[0] if ':' in collections_class else eval(collections_class)
        self.alembic_config = {k: v for k, v in upgrade.items() if v is not None}
        self.configs = configs

        self.metadatas = {}
        self.populates = []

    @staticmethod
    def handle_interactive():
        return {'session': session}

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

    def _configure_engine(self, name, engines, uri, debug, metadata, populate, **config):
        metadata = reference.load_object(metadata)[0]

        if uri:
            key = (uri, frozenset(config.items()), debug)
            engine = engines.setdefault(key, engine_from_config(config, '', echo=debug, url=uri))
            metadata.bind = engine

        self.metadatas[name] = metadata

        return populate

    def handle_start(self, app):
        engines = {}
        for name, config in self.configs.items():
            if config.pop('activated'):
                engine_config = self._configure_session(**config)
                populate = self._configure_engine(name, engines, **engine_config)

                self.populates.append(reference.load_object(populate)[0])

        configure_mappers(self.collections_class)

    def create_all(self):
        for metadata in self.metadatas.values():
            metadata.create_all()

    def drop_all(self):
        for metadata in self.metadatas.values():
            engine = metadata.bind

            alembic = MigrationContext.configure(url=engine.url)
            alembic._version.drop(engine.connect(), checkfirst=True)

            metadata.drop_all()

    def populate_all(self, app, services_service):
        for populate in self.populates:
            services_service(populate, app)
