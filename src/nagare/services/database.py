# --
# Copyright (c) 2008-2024 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --

import os

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse

import zope.sqlalchemy
from sqlalchemy import MetaData, orm, event, engine_from_config
from sqlalchemy.ext import declarative

from nagare.server import reference
from nagare.services import plugin
from nagare.admin.alembic_commands import get_heads, drop_version, get_current_revision

from .database_exceptions import InvalidVersion


class Session(orm.Session):
    metadatas = {}

    def get_bind(self, mapper=None, **kw):
        metadata = get_metadata(mapper.class_) if mapper is not None else None

        return self.metadatas[metadata] if metadata is not None else super().get_bind(mapper, **kw)


def get_metadata(cls):
    return getattr(cls, 'metadata', None)


def get_metadatas():
    return list(Session.metadatas)


def get_engine(metadata):
    return Session.metadatas.get(metadata)


session = orm.scoped_session(orm.sessionmaker(class_=Session, future=True))
query = session.query
metadata = MetaData()


def configure_database(
    uri,
    name=None,
    metadata=metadata,
    debug=False,
    json_serializer=None,
    json_deserializer=None,
    **config,
):
    if not isinstance(metadata, MetaData):
        metadata = reference.load_object(metadata)[0]

    if name is not None:
        metadata.name = name

    for event_name in ('before_create', 'after_create', 'before_drop', 'after_drop'):
        event_callback = config.pop(event_name, None)
        if event_callback:
            event.listen(metadata, event_name, reference.load_object(event_callback)[0])

    dialect, _, _ = urlparse.urlparse(uri).scheme.partition('+')
    if dialect == 'postgres':
        uri = 'postgresql' + uri[8:]

    if json_serializer:
        config['json_serializer'] = reference.load_object(json_serializer)[0]
    if json_deserializer:
        config['json_deserializer'] = reference.load_object(json_deserializer)[0]

    Session.metadatas[metadata] = engine = engine_from_config(config, '', echo=debug, url=uri, future=True)

    return engine


class EntityMetaBase(declarative.DeclarativeMeta):
    pass


class FKRelationshipBase(object):
    pass


def default_populate(app):
    pass


def configure_mappers(collections_class=set, inverse_foreign_keys=False):
    classes = []

    @event.listens_for(orm.Mapper, 'mapper_configured')
    def config(mapper, cls):
        classes.append(cls)
        for key, value in list(cls.__dict__.items()):
            if isinstance(value, FKRelationshipBase):
                delattr(cls, key)
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
            'uri': 'string(help="Database connection string")',
            'debug': 'boolean(default=False)',  # Set the database engine in debug mode?
            'session': 'string(default="nagare.database:session")',
            'autoflush': 'boolean(default=True)',
            'autocommit': 'boolean(default=False)',
            'expire_on_commit': 'boolean(default=True)',
            'twophases': 'boolean(default=False)',
            'json_serializer': 'string(default=None)',
            'json_deserializer': 'string(default=None)',
            'metadata': 'string(default="nagare.database:metadata")',  # Database metadata: entities description
            'populate': 'string(default="nagare.services.database:default_populate")',
            'before_create': 'string(default=None)',
            'after_create': 'string(default=None)',
            'before_drop': 'string(default=None)',
            'after_drop': 'string(default=None)',
        },
        upgrade={
            'file_template': 'string(default="%(year)d%(month).2d%(day).2d_%(rev)s_%(slug)s")',
            'timezone': 'string(default=None)',
            'truncate_slug_length': 'integer(default=None)',
            'revision_environment': 'boolean(default=None)',
            'sourceless': 'boolean(default=None)',
            'output_encoding': 'string(default=None)',
            'directory': 'string(default="$data/database_versions")',
            'version_check': 'boolean(default=None)',
            'version_validation': 'boolean(default=True)',
        },
    )

    def __init__(self, name, dist, collections_class, inverse_foreign_keys, upgrade, reloader_service=None, **configs):
        super(Database, self).__init__(
            name,
            dist,
            collections_class=collections_class,
            inverse_foreign_keys=inverse_foreign_keys,
            upgrade=upgrade.copy(),
            **configs,
        )

        self.collections_class = (
            reference.load_object(collections_class)[0] if ':' in collections_class else eval(collections_class)
        )
        self.inverse_foreign_keys = inverse_foreign_keys
        version_check = upgrade.pop('version_check')
        self.version_check = (reloader_service is None) if version_check is None else version_check
        self.version_validation = upgrade.pop('version_validation')
        self.alembic_config = {k: v for k, v in upgrade.items() if v is not None}
        self.configs = configs

        self.location = (
            os.path.join(dist.editable_project_location, 'src') if dist.editable_project_location else dist.location
        )
        self.populates = {}

    get_metadata = staticmethod(get_metadata)
    get_engine = staticmethod(get_engine)

    @property
    def metadatas(self):
        return get_metadatas()

    @staticmethod
    def handle_interaction():
        return {'session': session}

    @staticmethod
    def _configure_session(session, autoflush, autocommit, expire_on_commit, twophases, **engine_config):
        session = reference.load_object(session)[0]
        session.configure(
            autoflush=autoflush, autocommit=autocommit, expire_on_commit=expire_on_commit, twophase=twophases
        )

        zope.sqlalchemy.register(session)

        return engine_config

    def handle_start(self, app):
        for name, config in self.configs.items():
            if isinstance(config, dict) and config.pop('activated'):
                populate = config.pop('populate')
                self.populates[name] = reference.load_object(populate)[0]

                engine_config = self._configure_session(**config)
                configure_database(name=name, **engine_config)

        configure_mappers(self.collections_class, self.inverse_foreign_keys)

    def handle_serve(self, app):
        for metadata, engine in Session.metadatas.items():
            if self.version_check:
                heads = get_heads(metadata.name, self)
                if heads is not None:
                    current_revision = get_current_revision(engine)

                    if current_revision is None:
                        msg = 'Database version missing'
                    elif current_revision not in heads:
                        msg = 'Database version is not a revisions head'
                    else:
                        msg = None

                    if msg:
                        if self.version_validation:
                            raise InvalidVersion(msg)
                        else:
                            self.logger.error(msg)

    def create_all(self, db):
        for metadata in self.metadatas:
            if (db is None) or (db == metadata.name):
                engine = self.get_engine(metadata)
                metadata.create_all(engine)

    def drop_all(self, db):
        for metadata in self.metadatas:
            if (db is None) or (db == metadata.name):
                engine = self.get_engine(metadata)
                drop_version(engine)
                metadata.drop_all(engine)

    def populate_all(self, db, app, services_service):
        for db in [db] if db is not None else self.populates:
            services_service(self.populates[db], app)
