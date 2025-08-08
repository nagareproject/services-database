# Encoding: utf-8

# --
# Copyright (c) 2008-2025 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --

import pytest

from sqlalchemy import Text

from nagare.database import configure_database, metadata, session, configure_mappers
from nagare.database import Entity, Field, OneToOne, ManyToOne


class Car4_1(Entity):
    name = Field(Text)
    engine = OneToOne('Engine4_1')


class Engine4_1(Entity):
    name = Field(Text)


class Car4_2(Entity):
    name = Field(Text)
    engine = OneToOne('Engine4_2', inverse='car')


class Engine4_2(Entity):
    name = Field(Text)


class Car4_3(Entity):
    name = Field(Text)
    engine = OneToOne('Engine4_3', inverse='car')


class Engine4_3(Entity):
    name = Field(Text)
    car = ManyToOne('Car4_3', inverse='engine')


class Car4_4(Entity):
    name = Field(Text)
    engine = OneToOne('Engine4_4')


class Engine4_4(Entity):
    name = Field(Text)
    car = ManyToOne('Car4_4')


configure_mappers()

engine = configure_database('sqlite://')
metadata.create_all(engine)


def test1():
    car = Car4_1(name='onetoone_test1')
    engine = Engine4_1(name='onetoone_test1')

    car.engine = engine

    session.commit()

    assert car.engine.name == 'onetoone_test1'

    with pytest.raises(AttributeError, match="'car'"):
        engine.car


def test2():
    engine = Engine4_2(name='onetoone_test2_2')
    car = Car4_2(name='onetoone_test2_1', engine=engine)

    session.commit()

    assert car.engine.name == 'onetoone_test2_2'
    assert engine.car.name == 'onetoone_test2_1'


def test3():
    car = Car4_2(name='onetoone_test3_1')
    engine = Engine4_2(name='onetoone_test3_2', car=car)

    session.commit()

    assert car.engine.name == 'onetoone_test3_2'
    assert engine.car.name == 'onetoone_test3_1'


def test4():
    engine = Engine4_3(name='onetoone_test4_2')
    car = Car4_3(name='onetoone_test4_1', engine=engine)

    session.commit()

    assert car.engine.name == 'onetoone_test4_2'
    assert engine.car.name == 'onetoone_test4_1'


def test5():
    car = Car4_3(name='onetoone_test5_1')
    engine = Engine4_3(name='onetoone_test5_2', car=car)

    session.commit()

    assert car.engine.name == 'onetoone_test5_2'
    assert engine.car.name == 'onetoone_test5_1'


def test6():
    engine = Engine4_4(name='onetoone_test6_2')
    car = Car4_4(name='onetoone_test6_1', engine=engine)

    session.commit()

    assert car.engine.name == 'onetoone_test6_2'
    assert engine.car.name == 'onetoone_test6_1'


def test7():
    car = Car4_4(name='onetoone_test7_1')
    engine = Engine4_4(name='onetoone_test7_2', car=car)

    session.commit()

    assert car.engine.name == 'onetoone_test7_2'
    assert engine.car.name == 'onetoone_test7_1'
