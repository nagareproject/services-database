# --
# Copyright (c) 2008-2018 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --

from sqlalchemy.ext import declarative
from sqlalchemy import Column as Field
from sqlalchemy import orm, event, Integer, ForeignKey, Table

from nagare.services import database


class FKRelationship(object):

    def __init__(self, target, colname=None, inverse=None, collection_class=set, **kw):
        self.target = target
        self.colname = colname
        self.inverse = inverse
        self.collection_class = collection_class
        self.relationship_kwargs = kw

    def target_cls(self, cls):
        return cls._decl_class_registry.get(self.target)

    def find_inverse(self, local_cls, key, target_cls):
        if self.inverse:
            target_rel_name, target_rel = self.inverse, getattr(target_cls, self.inverse, None)
        else:
            target_rels = [
                (name, rel)
                for name, rel in target_cls.__dict__.items()
                if(
                    isinstance(rel, FKRelationship) and (
                        self.RELATIONSHIP_NAME in rel.INVERSE_RELATIONSHIP_NAME
                    ) and (
                        rel.target_cls(target_cls) is local_cls
                    )
                )
            ]

            rels_with_inverse = [(name, rel) for name, rel in target_rels if rel.inverse == key]
            rels_without_inverse = [(name, rel) for name, rel in target_rels if rel.inverse is None]

            if (len(rels_with_inverse) > 1) or (not rels_with_inverse and (len(rels_without_inverse) > 1)):
                raise ValueError(
                    "Several relations in entity '%s' match as inverse of the '%s' relation in entity '%s'. "
                    "You should specify inverse relations manually by using the inverse keyword." % (
                        target_cls.__name__,
                        key,
                        local_cls.__name__
                    )
                )

            if len(rels_with_inverse) == 1:
                target_rel_name, target_rel = rels_with_inverse[0]

            elif len(rels_without_inverse) == 1:
                target_rel_name, target_rel = rels_without_inverse[0]

            else:
                target_rel_name = target_rel = None

        return target_rel_name, target_rel

    def config(self, local_cls, key):
        target_cls = self.target_cls(local_cls)
        if target_cls is None:
            raise ValueError('In %r, relation "%s", target table "%s" not found' % (local_cls, key, self.target))

        target_rel_name, target_rel = self.find_inverse(local_cls, key, target_cls)
        backref_uselist, relationship_kwargs = self._config(local_cls, target_cls, key, target_rel_name)

        if (target_rel_name is not None) and (target_rel is None):
            relationship_kwargs['backref'] = orm.backref(
                target_rel_name,
                uselist=backref_uselist,
                collection_class=self.collection_class
            )

        rel = orm.relationship(
            target_cls,
            collection_class=self.collection_class,
            **dict(relationship_kwargs, **self.relationship_kwargs)
        )
        setattr(local_cls, key, rel)

        if isinstance(target_rel, FKRelationship):
            target_rel.inverse = key


class OneToMany(FKRelationship):
    """Generates a one to many relationship"""

    RELATIONSHIP_NAME = 'OneToMany'
    INVERSE_RELATIONSHIP_NAME = ('ManyToOne',)

    def create_foreign_key(self, foreign_key_name, pk, target_cls, key, **kw):
        foreign_key_name = self.colname or ((foreign_key_name or pk.table.description) + '_' + pk.description)

        foreign_key = getattr(target_cls, foreign_key_name, None)
        if foreign_key is None:
            foreign_key = Field(foreign_key_name, pk.type, ForeignKey(pk), **kw)
            setattr(target_cls, foreign_key_name, foreign_key)

        return foreign_key

    def _config(self, local_cls, target_cls, key, target_rel_name):
        pk = list(local_cls.__table__.primary_key)[0]
        foreign_key = self.create_foreign_key(target_rel_name, pk, target_cls, key)

        return False, {'primaryjoin': foreign_key == pk}


class ManyToOne(OneToMany):
    """Generates a many to one relationship"""

    RELATIONSHIP_NAME = 'ManyToOne'
    INVERSE_RELATIONSHIP_NAME = ('OneToMany', 'OneToOne')

    def create_foreign_key(self, foreign_key_name, pk, target_cls, key, **kw):
        return super(ManyToOne, self).create_foreign_key(key, pk, target_cls, key, **kw)

    def _config(self, local_cls, target_cls, key, target_rel_name):
        _, relationship_kwargs = super(ManyToOne, self)._config(target_cls, local_cls, key, target_rel_name)

        return True, dict(relationship_kwargs, uselist=False)


class OneToOne(OneToMany):
    """Generates a one to one relationship"""

    RELATIONSHIP_NAME = 'OneToOne'
    INVERSE_RELATIONSHIP_NAME = ('ManyToOne',)

    def create_foreign_key(self, foreign_key_name, pk, target_cls, key, **kw):
        return super(OneToOne, self).create_foreign_key(foreign_key_name, pk, target_cls, key, unique=True, **kw)

    def _config(self, local_cls, target_cls, key, target_rel_name):
        _, relationship_kwargs = super(OneToOne, self)._config(local_cls, target_cls, key, target_rel_name)

        return False, dict(relationship_kwargs, uselist=False)


class ManyToMany(FKRelationship):
    """Generates a many to many relationship"""

    RELATIONSHIP_NAME = 'ManyToMany'
    INVERSE_RELATIONSHIP_NAME = ('ManyToMany',)

    def __init__(
            self,
            target,
            tablename=None, local_colname=None, remote_colname=None, table=None, table_kwargs=None,
            inverse=None, collection_class=set,
            **kw
    ):
        super(ManyToMany, self).__init__(target, '', inverse, collection_class, **kw)

        self.tablename = tablename
        self.local_colname = local_colname
        self.remote_colname = remote_colname
        self.table = table
        self.table_kwargs = table_kwargs or {}

    def _config(self, local_cls, target_cls, key, target_rel_name):
        tablename = self.tablename

        if not tablename:
            source_part = (local_cls.__name__ + ('_' + target_rel_name if target_rel_name else '')).lower()
            target_part = (target_cls.__name__ + '_' + key).lower()

            if target_rel_name and (source_part < target_part):
                tablename = (target_part, source_part)
            else:
                tablename = (source_part, target_part)

        local_pk = list(local_cls.__table__.primary_key)[0]
        local_pk_name = (local_pk.table.description + '_' + local_pk.description)
        target_pk = list(target_cls.__table__.primary_key)[0]
        target_pk_name = (target_pk.table.description + '_' + target_pk.description)

        table = self.table or Table(
            '%s__%s' % tablename,
            local_cls.metadata,
            Field(self.local_colname or local_pk_name, ForeignKey(local_pk), primary_key=True),
            Field(self.remote_colname or target_pk_name, ForeignKey(target_pk), primary_key=True),
            keep_existing=True,
            **self.table_kwargs
        )

        return True, {'secondary': table}


@event.listens_for(orm.mapper, 'mapper_configured')
def config(mapper, cls):
    for key, value in list(cls.__dict__.items()):
        if isinstance(value, FKRelationship):
            value.config(cls, key)

# -----------------------------------------------------------------------------


class EntityMeta(declarative.DeclarativeMeta):
    def __new__(meta, name, bases, ns):
        options = ns.pop('using_options', {})

        cls = super(EntityMeta, meta).__new__(meta, name, bases, ns)

        if bases and (bases[0].__name__ != '_NagareEntity'):
            meta.set_options(cls, **options)

        return cls

    @staticmethod
    def set_options(
            cls,
            metadata=None, session=None,
            tablename=None, shortname=False,
            auto_primarykey=True, auto_add=True
    ):
        cls.metadata = metadata or database.metadata
        cls.session = session or database.session
        cls.query = cls.session.query_property()
        cls.using_options = {
            'shortname': shortname,
            'auto_primarykey': auto_primarykey,
            'auto_add': auto_add
        }

        if not hasattr(cls, '__table__') and not hasattr(cls, '__tablename__'):
            if callable(tablename):
                tablename = tablename(cls)

            if not tablename:
                tablename = '' if shortname else (cls.__module__.replace('.', '_') + '_')
                tablename = (tablename + cls.__name__).lower()

            cls.__tablename__ = tablename

        if auto_primarykey:
            setattr(
                cls,
                auto_primarykey if isinstance(auto_primarykey, (str, type(u''))) else 'id',
                Field(Integer, primary_key=True)
            )


class _NagareEntity(object):

    def __init__(self, auto_add=None, **kw):
        auto_add = self.using_options['auto_add'] if auto_add is None else auto_add
        if auto_add:
            self.session.add(self)

        declarative.api._declarative_constructor(self, **kw)

    def flush(self, *args, **kw):
        return orm.object_session(self).flush([self], *args, **kw)

    def delete(self, *args, **kw):
        return orm.object_session(self).delete(self, *args, **kw)

    def expire(self, *args, **kw):
        return orm.object_session(self).expire(self, *args, **kw)

    def refresh(self, *args, **kw):
        return orm.object_session(self).refresh(self, *args, **kw)

    def expunge(self, *args, **kw):
        return orm.object_session(self).expunge(self, *args, **kw)

    @classmethod
    def count(cls):
        return cls.query.count()

    @classmethod
    def all(cls):
        return cls.query.all()

    @classmethod
    def first(cls):
        return cls.query.first()

    @classmethod
    def get(cls, ident):
        return cls.query.get(ident)

    @classmethod
    def get_by(cls, **kw):
        return cls.filter_by(**kw).first()

    @classmethod
    def single_by(cls, **kw):
        return cls.filter_by(**kw).one_or_none()

    @classmethod
    def one_by(cls, **kw):
        return cls.filter_by(**kw).one()

    @classmethod
    def filter(cls, *criterion):
        return cls.query.filter(*criterion)

    @classmethod
    def filter_by(cls, **kw):
        return cls.query.filter_by(**kw)

    @classmethod
    def exists(cls, **kw):
        return cls.query.filter(cls.query.filter_by(**kw).exists()).count()

# -----------------------------------------------------------------------------


Entity = declarative.declarative_base(
    name='Entity',
    metaclass=EntityMeta,
    cls=_NagareEntity, constructor=_NagareEntity.__init__
)
