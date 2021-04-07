# --
# Copyright (c) 2008-2021 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --

from sqlalchemy import Column as Field
from sqlalchemy import orm, Integer, ForeignKey, Table

from nagare.services import database


class FKRelationship(database.FKRelationshipBase):
    RELATIONSHIP_NAME = ''
    INVERSE_RELATIONSHIP_NAME = ()

    def __init__(self, target, colname=None, inverse=None, collection_class=None, **kw):
        self.target = target
        self.colname = colname
        self.inverse = inverse
        self.collection_class = collection_class
        self.relationship_kwargs = kw

    def target_cls(self, cls):
        return cls.registry._class_registry.get(self.target)

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
                    "Several relations in entity '{}' match as inverse of the '{}' relation in entity '{}'. "
                    "You should specify inverse relations manually by using the inverse keyword.".format(
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

    def config(self, local_cls, key, collection_class, inverse_foreign_keys):
        target_cls = self.target_cls(local_cls)
        if target_cls is None:
            raise ValueError('In {}, relation "{}", target table "{}" not found'.format(local_cls, key, self.target))

        target_rel_name, target_rel = self.find_inverse(local_cls, key, target_cls)
        backref_uselist, relationship_kwargs = self._config(
            inverse_foreign_keys,
            local_cls, target_cls,
            key, target_rel_name
        )

        if (target_rel_name is not None) and (target_rel is None):
            relationship_kwargs['backref'] = orm.backref(
                target_rel_name,
                uselist=backref_uselist,
                collection_class=self.collection_class or collection_class
            )

        rel = orm.relationship(
            target_cls,
            collection_class=self.collection_class or collection_class,
            overlaps=target_rel_name,
            **relationship_kwargs
        )
        setattr(local_cls, key, rel)

        if isinstance(target_rel, FKRelationship):
            target_rel.inverse = key


class OneToMany(FKRelationship):
    """Generates a one to many relationship"""

    RELATIONSHIP_NAME = 'OneToMany'
    INVERSE_RELATIONSHIP_NAME = ('ManyToOne',)

    @staticmethod
    def create_foreign_key(pk, onupdate=None, ondelete=None, **kw):
        return ForeignKey(pk, onupdate=onupdate, ondelete=ondelete), kw

    @staticmethod
    def create_foreign_field_params(index=True, nullable=True, primary_key=False, **kw):
        return {'index': index, 'nullable': nullable, 'primary_key': primary_key}, kw

    def create_foreign_field(self, foreign_key_name, pk, target_cls, key):
        foreign_field_params = target_cls.get_params_of_field(foreign_key_name)
        foreign_key, foreign_field_params = self.create_foreign_key(pk, **foreign_field_params)
        foreign_field_params, kw = self.create_foreign_field_params(**foreign_field_params)

        foreign_key_name = self.colname or ((foreign_key_name or pk.table.description) + '_' + pk.description)
        foreign_key_field = getattr(target_cls, foreign_key_name, None)

        if foreign_key_field is None:
            foreign_key_field = Field(foreign_key_name, pk.type, foreign_key, **foreign_field_params)
            setattr(target_cls, foreign_key_name, foreign_key_field)

        return foreign_key_field, kw

    def _config(self, inverse_foreign_keys, local_cls, target_cls, key, target_rel_name):
        pk = list(local_cls.__table__.primary_key)[0]
        foreign_key, _ = self.create_foreign_field(target_rel_name, pk, target_cls, key)

        return False, dict(local_cls.get_params_of_field(key), primaryjoin=foreign_key == pk)


class ManyToOne(OneToMany):
    """Generates a many to one relationship"""

    RELATIONSHIP_NAME = 'ManyToOne'
    INVERSE_RELATIONSHIP_NAME = ('OneToMany', 'OneToOne')

    def create_foreign_field(self, foreign_key_name, pk, target_cls, key):
        return super(ManyToOne, self).create_foreign_field(key, pk, target_cls, key)

    def _config(self, inverse_foreign_keys, local_cls, target_cls, key, target_rel_name):
        _, kw = super(ManyToOne, self)._config(inverse_foreign_keys, target_cls, local_cls, key, target_rel_name)
        kw['uselist'] = False

        return True, kw


class OneToOne(OneToMany):
    """Generates a one to one relationship"""

    RELATIONSHIP_NAME = 'OneToOne'
    INVERSE_RELATIONSHIP_NAME = ('ManyToOne',)
    FOREIGN_KEY_PARAMS = {'index': True, 'unique': True}

    def create_foreign_field(self, foreign_key_name, pk, target_cls, key, **kw):
        return super(OneToOne, self).create_foreign_field(foreign_key_name, pk, target_cls, key, **kw)

    def _config(self, inverse_foreign_keys, local_cls, target_cls, key, target_rel_name, **kw):
        _, kw = super(OneToOne, self)._config(inverse_foreign_keys, local_cls, target_cls, key, target_rel_name, **kw)
        kw['uselist'] = False

        return False, kw


class ManyToMany(FKRelationship):
    """Generates a many to many relationship"""

    RELATIONSHIP_NAME = 'ManyToMany'
    INVERSE_RELATIONSHIP_NAME = ('ManyToMany',)

    def __init__(
            self,
            target,
            tablename=None, local_colname=None, remote_colname=None, table=None, table_kwargs=None,
            inverse=None, collection_class=None,
            **kw
    ):
        super(ManyToMany, self).__init__(target, '', inverse, collection_class, **kw)

        self.tablename = tablename
        self.local_colname = local_colname
        self.remote_colname = remote_colname
        self.table = table
        self.table_kwargs = table_kwargs or {}

    @staticmethod
    def create_foreign_key(pk, onupdate=None, ondelete=None, **kw):
        return ForeignKey(pk, onupdate=onupdate, ondelete=ondelete), kw

    @staticmethod
    def create_foreign_field_params(index=True, nullable=False, primary_key=True, **kw):
        return {'index': index, 'nullable': nullable, 'primary_key': primary_key}, kw

    def _config(self, inverse_foreign_keys, local_cls, target_cls, key, target_rel_name):
        tablename = self.tablename
        if not tablename:
            source_part = (local_cls.__tablename__ + '_' + key).lower()
            target_part = (target_cls.__tablename__ + ('_' + target_rel_name if target_rel_name else '')).lower()

            if target_rel_name and (source_part < target_part):
                tablename = (target_part, source_part)
            else:
                tablename = (source_part, target_part)

        local_pk = list(local_cls.__table__.primary_key)[0]
        local_pk_name = (local_pk.table.description + '_' + local_pk.description)
        target_pk = list(target_cls.__table__.primary_key)[0]
        target_pk_name = (target_pk.table.description + '_' + target_pk.description)

        foreign_field_params1 = target_cls.get_params_of_field(target_rel_name)
        foreign_key1, foreign_field_params1 = self.create_foreign_key(target_pk, **foreign_field_params1)
        foreign_field_params1, _ = self.create_foreign_field_params(**foreign_field_params1)
        foreign_name1 = self.remote_colname or target_pk_name

        foreign_field_params2 = local_cls.get_params_of_field(key)
        foreign_key2, foreign_field_params2 = self.create_foreign_key(local_pk, **foreign_field_params2)
        foreign_field_params2, kw = self.create_foreign_field_params(**foreign_field_params2)
        foreign_name2 = self.local_colname or local_pk_name

        if inverse_foreign_keys:
            foreign_name1, foreign_name2 = foreign_name2, foreign_name1

        table = self.table or Table(
            '{}__{}'.format(*tablename),
            local_cls.metadata,
            Field(foreign_name1, foreign_key1, **foreign_field_params1),
            Field(foreign_name2, foreign_key2, **foreign_field_params2),

            keep_existing=True,
            **self.table_kwargs
        )

        kw['secondary'] = table

        return True, kw

# -----------------------------------------------------------------------------


class EntityMeta(database.EntityMetaBase):
    def __new__(meta, name, bases, ns):
        options = ns.pop('using_options', {})

        cls = super(EntityMeta, meta).__new__(meta, name, bases, ns)

        if bases and (bases[0].__name__ != '_NagareEntity'):
            meta.set_options(cls, **options)

            cls.__relationships_params__ = {}
            for name, relationship in ns.items():
                if isinstance(relationship, FKRelationship):
                    cls.set_params_of_field(name, relationship.relationship_kwargs)
                    del relationship.relationship_kwargs

        return cls

    def set_params_of_field(cls, field, params):
        cls.__relationships_params__[field] = params

    def get_params_of_field(cls, field):
        return cls.__relationships_params__.get(field, {})

    def del_params_of_field(cls):
        del cls.__relationships_params__

    @staticmethod
    def set_options(
            cls,
            metadata=None, session=None,
            tablename=None, shortname=False,
            auto_primarykey=True, auto_add=True
    ):
        cls.metadata = metadata or database.metadata
        cls.session = session or database.session
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
    declarative_constructor = orm.declarative_base().__init__

    def __init__(self, auto_add=None, **kw):
        auto_add = self.using_options['auto_add'] if auto_add is None else auto_add
        if auto_add:
            self.session.add(self)

        self.declarative_constructor(**kw)

    def set(self, **kw):
        for key, value in kw.items():
            setattr(self, key, value)

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


Entity = orm.declarative_base(
    name='Entity',
    metaclass=EntityMeta,
    cls=_NagareEntity,
    constructor=_NagareEntity.__init__
)
