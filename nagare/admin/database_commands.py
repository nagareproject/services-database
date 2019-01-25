# --
# Copyright (c) 2008-2019 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --

from nagare.admin import command


class Commands(command.Commands):
    DESC = 'RDBMS subcommands'


class Create(command.Command):
    DESC = 'create all database tables'
    WITH_STARTED_SERVICES = True

    def set_arguments(self, parser):
        super(Create, self).set_arguments(parser)

        parser.add_argument(
            '--drop', action='store_true',
            help='drop the database tables before to re-create them'
        )

    @staticmethod
    def run(database_service, application_service, drop=False):
        if drop:
            database_service.drop_all()

        database_service.create_all()
        database_service.populate_all(application_service.service)


class Drop(command.Command):
    DESC = 'drop all database tables'
    WITH_STARTED_SERVICES = True

    @staticmethod
    def run(database_service):
        database_service.drop_all()
