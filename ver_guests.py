#!/usr/bin/python

from clases import Administrador
from configuracion import config

from sys import argv, exit


if len(argv) == 2:
    if argv[1] in config.creds.keys():
        # me quedo solo con la configuracion del host donde voy a buscar el
        # guest, para acelerar el proceso de conexion
        config.creds = {argv[1]: config.creds[argv[1]]}
        a = Administrador(config)
    else:
        print "No existe el host %s en la config" % argv[1]
        exit()
else:
    a = Administrador(config)


for h in a.hosts.values():
    print h
    for g in h.guests.values():
        print "\t", g
