# --
# Copyright (c) 2008-2024 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --

import os
import csv

from sqlalchemy import Unicode
from nagare.database import metadata, session, configure_mappers, configure_database
from nagare.database import Entity, Field, OneToMany, ManyToOne


class Language(Entity):
    using_options = {'auto_primarykey': False}

    id = Field(Unicode(50), primary_key=True)
    label = Field(Unicode(50))


class Father(Entity):
    name = Field(Unicode(100))
    children = OneToMany('Child')


class Child(Entity):
    name = Field(Unicode(100))
    father = ManyToOne('Father')


configure_mappers(list)


def setup_function(_):
    engine = configure_database('sqlite://')
    metadata.create_all(engine)


def test_1():
    Language(id=u'english', label=u'hello world')
    session.flush()

    language = Language.all()[0]
    assert language.id == u'english'
    assert language.label == u'hello world'

    Language(id=u'french', label=u'bonjour monde')
    session.flush()

    language = Language.all()[1]
    assert language.id == u'french'
    assert language.label == u'bonjour monde'


def test_2():
    """database - simple test with sqlalchemy/elixir unicode test"""
    file_path = os.path.join(os.path.dirname(__file__), 'helloworld.csv')
    try:
        f = open(file_path, 'r', encoding='utf-8')
    except TypeError:
        f = open(file_path, 'r')
    reader = csv.reader(f)

    res = {}
    for lang, label in reader:
        if not isinstance(lang, type(u'')):
            lang = lang.decode('utf-8')
        if not isinstance(label, type(u'')):
            label = label.decode('utf-8')

        res[lang] = label
        Language(id=lang, label=label)
    session.flush()

    for language in Language.all():
        assert language.label == res[language.id]


def test4():
    """database - test children relation with sqlalchemy/elixir"""
    f = Father(name=u'Father')

    c1 = Child(name=u'Child1')
    c2 = Child(name=u'Child2')

    f.children.append(c1)
    f.children.append(c2)
    session.flush()

    assert f is c1.father
    assert f is c2.father

    assert all(elt.father.id == f.id for elt in Child.all())
