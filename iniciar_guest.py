#!/usr/bin/python

from clases import Administrador

from configuracion import config

a = Administrador(config)
for h in a.hosts:
    print h
    for g in h.guests:
        if g.name == 'prueba':
            g.iniciar(sync_run=True)
