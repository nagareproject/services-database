# --
# Copyright (c) 2008-2022 Net-ng.
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

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse

import zope.sqlalchemy
from sqlalchemy.ext import declarative
from sqlalchemy import orm, event, MetaData, engine_from_config
from alembic import command, migration
from alembic import config as alembic_config

from nagare.services import plugin
from nagare.server import reference

from .database_exceptions import InvalidVersion


session = orm.scoped_session(orm.sessionmaker())
query = session.query
metadata = MetaData()


class AlembicConfig(alembic_config.Config):
    def __init__(self, **config):
        super(AlembicConfig, self).__init__()

        self.file_config = RawConfigParser()
        for k, v in config.items():
            self.set_main_option(k, v)

    def get_template_directory(self):
        here = os.path.abspath(os.path.dirname(__file__))
        return os.path.abspath(os.path.join(here, '..', 'templates'))


class EntityMetaBase(declarative.DeclarativeMeta):
    pass


class FKRelationshipBase(object):
    pass


def default_populate(app):
    pass


def configure_mappers(collections_class=set, inverse_foreign_keys=False):
    classes = []

    @event.listens_for(orm.mapper, 'mapper_configured')
    def config(mapper, cls):
        classes.append(cls)
        for key, value in list(cls.__dict__.items()):
            if isinstance(value, FKRelationshipBase):
                value.config(cls, key, collections_class, inverse_foreign_keys)

    orm.configure_mappers()

    for cls in classes:
        if isinstance(cls, EntityMetaBase):
            cls.del_params_of_field()
            cls.query = cls.session.query_property()


class Database(plugin.Plugin):
    CONFIG_SPEC = dict(
        plugin.Plugin.CONFIG_SPEC,
        collections_class='string(default=set)',
        inverse_foreign_keys='boolean(default=False)',

        __many__={  # Database sub-sections
            'activated': 'boolean(default=True)',
            'uri': 'string(default=None, help="Database connection string")',
            'debug': 'boolean(default=False)',  # Set the database engine in debug mode?

            'session': 'string(default="nagare.database:session")',
            'autoflush': 'boolean(default=True)',
            'autocommit': 'boolean(default=False)',
            'expire_on_commit': 'boolean(default=True)',
            'twophases': 'boolean(default=False)',
            'json_serializer': 'string(default=None)',
            'json_deserializer': 'string(default=None)',

            'metadata': 'string(default="nagare.database:metadata")',  # Database metadata: database entities description
            'populate': 'string(default="nagare.services.database:default_populate")'
        },

        upgrade={
            'file_template': 'string(default=None)',
            'timezone': 'string(default=None)',
            'truncate_slug_length': 'integer(default=None)',
            'revision_environment': 'boolean(default=None)',
            'sourceless': 'boolean(default=None)',
            'output_encoding': 'string(default=None)',
            'directory': 'string(default="$data/database_versions")',
            'version_check': 'boolean(default=None)',
            'version_validation': 'boolean(default=True)'
        }
    )

    def __init__(
        self,
        name, dist,
        collections_class,
        inverse_foreign_keys,
        upgrade,
        reloader_service=None,
        **configs
    ):
        super(Database, self).__init__(
            name, dist,
            collections_class=collections_class,
            inverse_foreign_keys=inverse_foreign_keys,
            upgrade=upgrade.copy(),
            **configs)

        self.collections_class = reference.load_object(collections_class)[0] if ':' in collections_class else eval(collections_class)
        self.inverse_foreign_keys = inverse_foreign_keys
        version_check = upgrade.pop('version_check')
        self.version_check = (reloader_service is None) if version_check is None else version_check
        self.version_validation = upgrade.pop('version_validation')
        self.alembic_config = {k: v for k, v in upgrade.items() if v is not None}
        self.configs = configs

        self.metadatas = {}
        self.populates = []

    @staticmethod
    def handle_interaction():
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

    @staticmethod
    def convert_uri(uri):
        dialect, _, _ = urlparse.urlparse(uri).scheme.partition('+')
        if dialect == 'postgres':
            uri = 'postgresql' + uri[8:]

        return uri

    def get_script_location(self, db):
        return os.path.join(self.alembic_config['directory'], db)

    def get_alembic_config(self, db, **config):
        return AlembicConfig(**dict(
            self.alembic_config,
            script_location=self.get_script_location(db),
            **config
        ))

    def get_metadata(self, name):
        return self.metadatas[name]

    def get_engine(self, name):
        return self.get_metadata(name).bind

    def _configure_engine(
            self,
            name,
            engines, uri, debug, metadata, populate,
            json_serializer, json_deserializer, **config
    ):
        metadata = reference.load_object(metadata)[0]

        if uri:
            uri = self.convert_uri(uri)

            if json_serializer:
                config['json_serializer'] = reference.load_object(json_serializer)[0]
            if json_deserializer:
                config['json_deserializer'] = reference.load_object(json_deserializer)[0]

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

        configure_mappers(self.collections_class, self.inverse_foreign_keys)

    def handle_serve(self, app):
        for name in self.configs:
            script_location = self.get_script_location(name)
            if self.version_check and os.access(script_location, os.F_OK):
                alembic_config = self.get_alembic_config(name)
                heads = command.ScriptDirectory.from_config(alembic_config).get_heads()

                with self.get_engine(name).connect() as connection:
                    migration_context = migration.MigrationContext.configure(connection)
                    current_revision = migration_context.get_current_revision()

                if current_revision is None:
                    msg = 'Database version missing'
                elif current_revision not in heads:
                    msg = 'Database version not a revisions head'
                else:
                    msg = None

                if msg:
                    if self.version_validation:
                        raise InvalidVersion(msg)
                    else:
                        self.logger.error(msg)

    def create_all(self):
        for metadata in self.metadatas.values():
            metadata.create_all()

    def drop_all(self):
        for metadata in self.metadatas.values():
            engine = metadata.bind

            alembic = migration.MigrationContext.configure(url=engine.url)
            alembic._version.drop(engine.connect(), checkfirst=True)

            metadata.drop_all()

    def populate_all(self, app, services_service):
        for populate in self.populates:
            services_service(populate, app)
