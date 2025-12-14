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

from nagare.database import Field, Entity, ManyToMany, session, metadata, configure_mappers, configure_database


class Movie3_1(Entity):
    name = Field(Text)
    tags = ManyToMany('Tag3_1')


class Tag3_1(Entity):
    name = Field(Text)


class Movie3_2(Entity):
    name = Field(Text)
    tags = ManyToMany('Tag3_2', inverse='movies')


class Tag3_2(Entity):
    name = Field(Text)


class Movie3_3(Entity):
    name = Field(Text)
    tags = ManyToMany('Tag3_3', inverse='movies')


class Tag3_3(Entity):
    name = Field(Text)
    movies = ManyToMany('Movie3_3')


class Movie3_4(Entity):
    name = Field(Text)
    tags = ManyToMany('Tag3_4')


class Tag3_4(Entity):
    name = Field(Text)
    movies = ManyToMany('Movie3_4')


configure_mappers(list)

engine = configure_database('sqlite://')
metadata.create_all(engine)


def test1():
    tag1 = Tag3_1(name='manytomany_test1_1')
    tag2 = Tag3_1(name='manytomany_test1_2')
    movie1 = Movie3_1(name='manytomany_test1_1', tags=[tag1])
    movie2 = Movie3_1(name='manytomany_test1_2')

    movie2.tags = [tag1]
    movie2.tags.append(tag2)

    session.commit()

    assert {tag.name for tag in movie1.tags} == {'manytomany_test1_1'}
    assert {tag.name for tag in movie2.tags} == {'manytomany_test1_1', 'manytomany_test1_2'}

    with pytest.raises(AttributeError, match="'movies'"):
        tag1.movies

    with pytest.raises(AttributeError, match="'movies'"):
        tag2.movies


def test2():
    tag1 = Tag3_2(name='manytomany_test2_1')
    tag2 = Tag3_2(name='manytomany_test2_2')
    movie1 = Movie3_2(name='manytomany_test2_1', tags=[tag1])
    movie2 = Movie3_2(name='manytomany_test2_2')

    movie2.tags = [tag1]
    movie2.tags.append(tag2)

    session.commit()

    assert {tag.name for tag in movie1.tags} == {'manytomany_test2_1'}
    assert {tag.name for tag in movie2.tags} == {'manytomany_test2_1', 'manytomany_test2_2'}

    assert {movie.name for movie in tag1.movies} == {'manytomany_test2_1', 'manytomany_test2_2'}
    assert {movie.name for movie in tag2.movies} == {'manytomany_test2_2'}


def test3():
    movie1 = Movie3_2(name='manytomany_test3_1')
    movie2 = Movie3_2(name='manytomany_test3_2')
    tag1 = Tag3_2(name='manytomany_test3_1', movies=[movie1])
    tag2 = Tag3_2(name='manytomany_test3_2')

    tag1.movies.append(movie2)
    tag2.movies = [movie2]

    session.commit()

    assert {tag.name for tag in movie1.tags} == {'manytomany_test3_1'}
    assert {tag.name for tag in movie2.tags} == {'manytomany_test3_1', 'manytomany_test3_2'}

    assert {movie.name for movie in tag1.movies} == {'manytomany_test3_1', 'manytomany_test3_2'}
    assert {movie.name for movie in tag2.movies} == {'manytomany_test3_2'}


def test4():
    movie1 = Movie3_2(name='manytomany_test4_1')
    movie2 = Movie3_2(name='manytomany_test4_2')
    tag1 = Tag3_2(name='manytomany_test4_1', movies=[movie1])
    tag2 = Tag3_2(name='manytomany_test4_2')

    tag1.movies.append(movie2)
    tag2.movies = [movie2]

    session.commit()

    assert {tag.name for tag in movie1.tags} == {'manytomany_test4_1'}
    assert {tag.name for tag in movie2.tags} == {'manytomany_test4_1', 'manytomany_test4_2'}

    assert {movie.name for movie in tag1.movies} == {'manytomany_test4_1', 'manytomany_test4_2'}
    assert {movie.name for movie in tag2.movies} == {'manytomany_test4_2'}


def test5():
    movie1 = Movie3_2(name='manytomany_test5_1')
    movie2 = Movie3_2(name='manytomany_test5_2')
    tag1 = Tag3_2(name='manytomany_test5_1', movies=[movie1])
    tag2 = Tag3_2(name='manytomany_test5_2')

    tag1.movies.append(movie2)
    tag2.movies = [movie2]

    session.commit()

    assert {tag.name for tag in movie1.tags} == {'manytomany_test5_1'}
    assert {tag.name for tag in movie2.tags} == {'manytomany_test5_1', 'manytomany_test5_2'}

    assert {movie.name for movie in tag1.movies} == {'manytomany_test5_1', 'manytomany_test5_2'}
    assert {movie.name for movie in tag2.movies} == {'manytomany_test5_2'}
