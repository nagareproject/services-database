# Encoding: utf-8

# --
# Copyright (c) 2008-2018 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --

import pytest

from sqlalchemy import orm, create_engine, Text

from nagare.database import metadata, session
from nagare.database.declarative import Entity, Field, OneToMany, ManyToOne


class Parent2_1(Entity):
    name = Field(Text)


class Child2_1(Entity):
    name = Field(Text)
    parent = ManyToOne('Parent2_1')


class Parent2_2(Entity):
    name = Field(Text)


class Child2_2(Entity):
    name = Field(Text)
    parent = ManyToOne('Parent2_2', inverse='children')


class Parent2_3(Entity):
    name = Field(Text)
    children = OneToMany('Child2_3', inverse='parent')


class Child2_3(Entity):
    name = Field(Text)
    parent = ManyToOne('Parent2_3')


class Parent2_4(Entity):
    name = Field(Text)
    children = OneToMany('Child2_4')


class Child2_4(Entity):
    name = Field(Text)
    parent = ManyToOne('Parent2_4')


orm.configure_mappers()

metadata.bind = create_engine('sqlite://')
metadata.create_all()


def test1():
    parent = Parent2_1(name='manytoone_test1')
    child1 = Child2_1(name='manytoone_test1_1', parent=parent)
    child2 = Child2_1(name='manytoone_test1_2')
    child2.parent = parent

    session.commit()

    assert child1.parent.name == 'manytoone_test1'
    assert child2.parent.name == 'manytoone_test1'

    with pytest.raises(AttributeError, match="'children'"):
        parent.children


def test2():
    parent = Parent2_2(name='manytoone_test2')
    child1 = Child2_2(name='manytoone_test2_1', parent=parent)
    child2 = Child2_2(name='manytoone_test2_2', )
    child2.parent = parent

    session.commit()

    assert child1.parent.name == 'manytoone_test2'
    assert child2.parent.name == 'manytoone_test2'
    assert {child.name for child in parent.children} == {'manytoone_test2_1', 'manytoone_test2_2'}


def test3():
    child1 = Child2_2(name='manytoone_test3_1')
    child2 = Child2_2(name='manytoone_test3_2')
    parent = Parent2_2(name='manytoone_test3')
    parent.children.append(child1)
    parent.children.append(child2)

    session.commit()

    assert child1.parent.name == 'manytoone_test3'
    assert child2.parent.name == 'manytoone_test3'
    assert {child.name for child in parent.children} == {'manytoone_test3_1', 'manytoone_test3_2'}


def test4():
    parent = Parent2_3(name='manytoone_test4')
    child1 = Child2_3(name='manytoone_test4_1', parent=parent)
    child2 = Child2_3(name='manytoone_test4_2')
    child2.parent = parent

    session.commit()

    assert child1.parent.name == 'manytoone_test4'
    assert child2.parent.name == 'manytoone_test4'
    assert {child.name for child in parent.children} == {'manytoone_test4_1', 'manytoone_test4_2'}


def test5():
    child1 = Child2_3(name='manytoone_test5_1')
    child2 = Child2_3(name='manytoone_test5_2')
    parent = Parent2_3(name='manytoone_test5')
    parent.children.append(child1)
    parent.children.append(child2)

    session.commit()

    assert child1.parent.name == 'manytoone_test5'
    assert child2.parent.name == 'manytoone_test5'
    assert {child.name for child in parent.children} == {'manytoone_test5_1', 'manytoone_test5_2'}


def test6():
    parent = Parent2_4(name='manytoone_test6')
    child1 = Child2_4(name='manytoone_test6_1', parent=parent)
    child2 = Child2_4(name='manytoone_test6_2')
    child2.parent = parent

    session.commit()

    assert child1.parent.name == 'manytoone_test6'
    assert child2.parent.name == 'manytoone_test6'
    assert {child.name for child in parent.children} == {'manytoone_test6_1', 'manytoone_test6_2'}


def test7():
    child1 = Child2_4(name='manytoone_test7_1')
    child2 = Child2_4(name='manytoone_test7_2')
    parent = Parent2_4(name='manytoone_test7')
    parent.children.append(child1)
    parent.children.append(child2)

    session.commit()

    assert child1.parent.name == 'manytoone_test7'
    assert child2.parent.name == 'manytoone_test7'
    assert {child.name for child in parent.children} == {'manytoone_test7_1', 'manytoone_test7_2'}
