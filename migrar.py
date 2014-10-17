#!/usr/bin/python

from clases import Administrador

from configuracion import config

a = Administrador(config)
#a.migrar('prueba', 'esxi2', 'esxi4')
a.migrar('prueba', 'esxi4', 'esxi2')
