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


class Parent1_1(Entity):
    name = Field(Text)
    children = OneToMany('Child1_1')


class Child1_1(Entity):
    name = Field(Text)


class Parent1_2(Entity):
    name = Field(Text)
    children = OneToMany('Child1_2', inverse='parent')


class Child1_2(Entity):
    name = Field(Text)


class Parent1_3(Entity):
    name = Field(Text)
    children = OneToMany('Child1_3')


class Child1_3(Entity):
    name = Field(Text)
    parent = ManyToOne('Parent1_3', inverse='children')


class Parent1_4(Entity):
    name = Field(Text)
    children = OneToMany('Child1_4')


class Child1_4(Entity):
    name = Field(Text)
    parent = ManyToOne('Parent1_4')


orm.configure_mappers()

metadata.bind = create_engine('sqlite://', echo=False)
metadata.create_all()


def test1():
    child1 = Child1_1(name='onetomany_test1_1')
    child2 = Child1_1(name='onetomany_test1_2')
    parent = Parent1_1(name='onetomany_test1', children={child1, child2})

    session.commit()

    assert {child.name for child in parent.children} == {'onetomany_test1_1', 'onetomany_test1_2'}

    with pytest.raises(AttributeError, match="'parent'"):
        child1.parent


def test2():
    child1 = Child1_1(name='onetomany_test2_1')
    child2 = Child1_1(name='onetomany_test2_2')
    parent = Parent1_1(name='onetomany_test2')
    parent.children.add(child1)
    parent.children.add(child2)

    session.commit()

    assert {child.name for child in parent.children} == {'onetomany_test2_1', 'onetomany_test2_2'}

    with pytest.raises(AttributeError, match="'parent'"):
        child1.parent


def test3():
    child1 = Child1_2(name='onetomany_test3_1')
    child2 = Child1_2(name='onetomany_test3_2')
    parent = Parent1_2(name='onetomany_test3', children={child1, child2})

    session.commit()

    assert {child.name for child in parent.children} == {'onetomany_test3_1', 'onetomany_test3_2'}
    assert child1.parent.name == 'onetomany_test3'
    assert child2.parent.name == 'onetomany_test3'


def test4():
    child1 = Child1_2(name='onetomany_test4_1')
    child2 = Child1_2(name='onetomany_test4_2')
    parent = Parent1_2(name='onetomany_test4')
    parent.children.add(child1)
    parent.children.add(child2)

    session.commit()

    assert {child.name for child in parent.children} == {'onetomany_test4_1', 'onetomany_test4_2'}
    assert child1.parent.name == 'onetomany_test4'
    assert child2.parent.name == 'onetomany_test4'


def test5():
    parent = Parent1_2(name='onetomany_test5')
    child1 = Child1_2(name='onetomany_test5_1', parent=parent)
    child2 = Child1_2(name='onetomany_test5_2')
    child2.parent = parent

    session.commit()

    assert {child.name for child in parent.children} == {'onetomany_test5_1', 'onetomany_test5_2'}
    assert child1.parent.name == 'onetomany_test5'
    assert child2.parent.name == 'onetomany_test5'


def test6():
    child1 = Child1_3(name='onetomany_test6_1')
    child2 = Child1_3(name='onetomany_test6_2')
    parent = Parent1_3(name='onetomany_test6', children={child1, child2})

    session.commit()

    assert {child.name for child in parent.children} == {'onetomany_test6_1', 'onetomany_test6_2'}
    assert child1.parent.name == 'onetomany_test6'
    assert child2.parent.name == 'onetomany_test6'


def test7():
    child1 = Child1_3(name='onetomany_test7_1')
    child2 = Child1_3(name='onetomany_test7_2')
    parent = Parent1_3(name='onetomany_test7')
    parent.children.add(child1)
    parent.children.add(child2)

    session.commit()

    assert {child.name for child in parent.children} == {'onetomany_test7_1', 'onetomany_test7_2'}
    assert child1.parent.name == 'onetomany_test7'
    assert child2.parent.name == 'onetomany_test7'


def test8():
    parent = Parent1_3(name='onetomany_test8')
    child1 = Child1_3(name='onetomany_test8_1', parent=parent)
    child2 = Child1_3(name='onetomany_test8_2')
    child2.parent = parent

    session.commit()

    assert {child.name for child in parent.children} == {'onetomany_test8_1', 'onetomany_test8_2'}
    assert child1.parent.name == 'onetomany_test8'
    assert child2.parent.name == 'onetomany_test8'


def test9():
    child1 = Child1_4(name='onetomany_test9_1')
    child2 = Child1_4(name='onetomany_test9_2')
    parent = Parent1_4(name='onetomany_test9', children={child1, child2})

    session.commit()

    assert {child.name for child in parent.children} == {'onetomany_test9_1', 'onetomany_test9_2'}
    assert child1.parent.name == 'onetomany_test9'
    assert child2.parent.name == 'onetomany_test9'


def test10():
    child1 = Child1_4(name='onetomany_test10_1')
    child2 = Child1_4(name='onetomany_test10_2')
    parent = Parent1_4(name='onetomany_test10')
    parent.children.add(child1)
    parent.children.add(child2)

    session.commit()

    assert {child.name for child in parent.children} == {'onetomany_test10_1', 'onetomany_test10_2'}
    assert child1.parent.name == 'onetomany_test10'
    assert child2.parent.name == 'onetomany_test10'


def test11():
    parent = Parent1_4(name='onetomany_test11')
    child1 = Child1_4(name='onetomany_test11_1', parent=parent)
    child2 = Child1_4(name='onetomany_test11_2')
    child2.parent = parent

    session.commit()

    assert {child.name for child in parent.children} == {'onetomany_test11_1', 'onetomany_test11_2'}
    assert child1.parent.name == 'onetomany_test11'
    assert child2.parent.name == 'onetomany_test11'
