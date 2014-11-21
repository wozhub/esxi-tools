#!/usr/bin/python

from clases import Administrador

from configuracion import config

a = Administrador(config)
for h in a.hosts:
    for g in h.guests:
        if g.name == 'prueba':
            g.respaldar()
            break
