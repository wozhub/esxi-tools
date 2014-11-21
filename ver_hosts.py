#!/usr/bin/python

from clases import Administrador

from configuracion import config

a = Administrador(config, configurarGuests=False)
for h in a.hosts:
    print h
