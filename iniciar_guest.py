#!/usr/bin/python

from clases import Administrador
from configuracion import config

from sys import argv

if len(argv) == 3:
    if argv[2] in config.creds.keys():
        # me quedo solo con la configuracion del host donde voy a buscar el
        # guest, para acelerar el proceso de conexion
        config.creds = {argv[2]: config.creds[argv[2]]}
        a = Administrador(config)
        a.iniciarGuest(argv[1], argv[2])
    else:
        print "No existe el host %s en la config" % argv[2]
elif len(argv) == 2:
    a = Administrador(config)
    a.iniciarGuest(argv[1])
