# Encoding: utf-8

# --
# Copyright (c) 2008-2018 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --

from os import path

from setuptools import setup, find_packages


here = path.normpath(path.dirname(__file__))

with open(path.join(here, 'README.rst')) as long_description:
    LONG_DESCRIPTION = long_description.read()

setup(
    name='nagare-services-database',
    author='Net-ng',
    author_email='alain.poirier@net-ng.com',
    description='RDBM service',
    long_description=LONG_DESCRIPTION,
    license='BSD',
    keywords='',
    url='https://github.com/nagareproject/services-database',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    setup_requires=['setuptools_scm', 'pytest-runner'],
    use_scm_version=True,
    install_requires=[
        'SQLAlchemy', 'Elixir', 'alembic', 'zope.sqlalchemy',
        'nagare-services-transaction', 'nagare-server'
    ],
    tests_require=['pytest'],
    entry_points='''
        [nagare.commands]
        db = nagare.admin.command:Commands

        [nagare.commands.db]
        create = nagare.admin.database_commands:Create
        drop = nagare.admin.database_commands:Drop
        init = nagare.admin.alembic_commands:Init
        stamp = nagare.admin.alembic_commands:Stamp
        revision = nagare.admin.alembic_commands:Revision
        upgrade = nagare.admin.alembic_commands:Upgrade
        downgrade = nagare.admin.alembic_commands:Downgrade
        current = nagare.admin.alembic_commands:Current
        history = nagare.admin.alembic_commands:History
        branches = nagare.admin.alembic_commands:Branches
        heads = nagare.admin.alembic_commands:Heads
        merge = nagare.admin.alembic_commands:Merge
        show = nagare.admin.alembic_commands:Show

        [nagare.services]
        database = nagare.services.database:Database
    '''
)
