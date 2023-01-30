# --
# Copyright (c) 2008-2023 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --

from __future__ import absolute_import

from pickle import PicklingError

from nagare.services import database
from sqlalchemy import event, orm


class NonSerializable(object):
    def __reduce__(self):
        raise PicklingError("SQLAlchemy entity <{}> can't be serialized".format(self.__class__.__name__))


def entity_getstate(entity):
    """Return the state of an SQLAlchemy entity.

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
    d = {k: v for k, v in entity.__dict__.items() if k not in attrs}

    # Keep only the primary key from the SQLAlchemy state
    d['_sa_key'] = state.key[1] if state.key else None

    return d


def entity_setstate(entity, d):
    """Set the state of an SQLAlchemy entity.

    In:
      - ``entity`` -- the newly created and not yet initialized SQLAlchemy entity
      - ``d`` -- the state dictionary (created by ``entity_getstate()``)
    """
    # Copy the _not_ SQLAlchemy managed attributes to our entity
    key = d.pop('_sa_key', None)
    entity.__dict__.update(d)

    if key is not None:
        # Fetch a new and initialized SQLAlchemy from the database
        session = getattr(entity.__class__, 'session', database.session)

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


@event.listens_for(orm.Mapper, 'instrument_class')
def add_pickle_hooks(mapper, cls):
    # Dynamically add a ``__getstate__()`` and ``__setstate__()`` method
    # to the SQLAlchemy entities
    if not hasattr(cls, '__getstate__'):
        cls.__getstate__ = entity_getstate

    if not hasattr(cls, '__setstate__'):
        cls.__setstate__ = entity_setstate
