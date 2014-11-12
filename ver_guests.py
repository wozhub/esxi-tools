#!/usr/bin/python

from clases import Administrador

from configuracion import config

a = Administrador(config)
for h in a.hosts.values():
    print h
    for g in h.guests.values():
        print "\t",g
