#!/usr/bin/python

from clases import Administrador

from configuracion import config

a = Administrador(config)
a.migrar('puppet', 'esxi3', 'esxi4')
a.migrar('http-dev', 'esxi3', 'esxi2')
a.migrar('cas', 'esxi3', 'esxi0')
a.migrar('pampa', 'esxi1', 'esxi0')
