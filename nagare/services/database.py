# --
# Copyright (c) 2008-2018 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --

import sqlalchemy


import zope.sqlalchemy
from nagare.services import plugin
from nagare.server import reference
from alembic.migration import MigrationContext

# ``sqlalchemy.orm.ScopedSession`` is needed by ``elixir``
from sqlalchemy import orm
orm.__dict__.setdefault('ScopedSession', orm.scoped_session)
from elixir import setup_all, session  # noqa: E402

# session.configure(autoflush=True, expire_on_commit=True, autocommit=True)
# session.configure(twophase=True)
zope.sqlalchemy.register(session)
query = session.query

# -----------------------------------------------------------------------------


def entity_getstate(entity):
    """Return the state of an SQLAlchemy entity

    In:
      - ``entity`` -- the SQLAlchemy entity

    Return:
      - the state dictionary
    """
    state = entity._sa_instance_state  # SQLAlchemy managed state

    if state.key:
        attrs = set(state.manager.local_attrs)  # SQLAlchemy managed attributes
        attrs.add('_sa_instance_state')
    else:
        attrs = ()

    # ``d`` is the dictionary of the _not_ SQLAlchemy managed attributes
    d = {k: v for k, v in entity.__dict__.iteritems() if k not in attrs}

    # Keep only the primary key from the SQLAlchemy state
    d['_sa_key'] = state.key[1] if state.key else None

    return d


def entity_setstate(entity, d):
    """Set the state of an SQLAlchemy entity

    In:
      - ``entity`` -- the newly created and not yet initialized SQLAlchemy entity
      - ``d`` -- the state dictionary (created by ``entity_getstate()``)
    """
    # Copy the _not_ SQLAlchemy managed attributes to our entity
    key = d.pop('_sa_key', None)
    entity.__dict__.update(d)

    if key is not None:
        # Fetch a new and initialized SQLAlchemy from the database
        x = session.query(entity.__class__).get(key)
        session.expunge(x)

        # Copy its state to our entity
        entity.__dict__.update(x.__dict__)

        # Adjust the entity SQLAlchemy state
        state = x._sa_instance_state.__getstate__()
        state['instance'] = entity
        entity._sa_instance_state.__setstate__(state)

        # Add the entity to the current database session
        session.add(entity)


def add_pickle_hooks(mapper, cls):
    # Dynamically add a ``__getstate__()`` and ``__setstate__()`` method
    # to the SQLAlchemy entities
    if not hasattr(cls, '__getstate__'):
        cls.__getstate__ = entity_getstate

    if not hasattr(cls, '__setstate__'):
        cls.__setstate__ = entity_setstate


sqlalchemy.event.listen(orm.Mapper, 'instrument_class', add_pickle_hooks)

# -----------------------------------------------------------------------------


def default_populate(app):
    pass


class Database(plugin.Plugin):
    CONFIG_SPEC = {
        'twophases': 'boolean(default=False)',
        '__many__': {  # Database sub-sections
            'activated': 'boolean(default=True)',
            'uri': 'string(default=None)',  # Database connection string
            'metadata': 'string(default=None)',  # Database metadata: database entities description
            'populate': 'string(default="nagare.services.database:default_populate")',
            'debug': 'boolean(default=False)'  # Set the database engine in debug mode?
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

    def __init__(self, name, dist, twophases, upgrade, **configs):
        super(Database, self).__init__(name, dist)

        self.alembic_config = {k: v for k, v in upgrade.items() if v is not None}
        self.configs = configs
        self.metadatas = []
        self.populates = []

        session.configure(twophase=twophases)

    def setup(self):
        self.populates = [reference.load_object(config['populate'])[0] for config in self.configs.values()]

        for config in self.configs.values():
            self._bind(**config)

        if self.metadatas:
            setup_all()

    def handle_start(self, app):
        self.setup()

    def _bind(self, activated, uri, metadata, populate, debug, **engine_config):
        if activated and uri and metadata:
            metadata = reference.load_object(metadata)[0]
            metadata.bind = sqlalchemy.engine_from_config(engine_config, '', echo=debug, url=uri)

            self.metadatas.append(metadata)

    def create_all(self):
        for metadata in self.metadatas:
            metadata.create_all()

    def drop_all(self):
        for metadata in self.metadatas:
            engine = metadata.bind

            alembic = MigrationContext.configure(url=engine.url)
            alembic._version.drop(engine.connect(), checkfirst=True)

            metadata.drop_all()

    def populate_all(self, app):
        for populate in self.populates:
            populate(app)
