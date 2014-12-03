#!/usr/bin/python

from clases import Administrador
from configuracion import config

import argparse
from IPython import embed
from sys import exit, stdout
from traceback import print_exc

p = argparse.ArgumentParser(description='---')

p.add_argument('--interactivo', action='store_true',
               default=argparse.SUPPRESS,
               help='Modo Interactivo mediante IPython')

p.add_argument('--host', dest='host', action='store',
               default=argparse.SUPPRESS,
               help='Host ESXi donde llevar al cabo las tareas')

p.add_argument('--guest', dest='guest', action='store',
               default=argparse.SUPPRESS,
               help='Guest ESXi donde llevar al cabo las tareas')


g = p.add_mutually_exclusive_group(required=True)

g.add_argument('--ver', action='store', choices=['hosts', 'guests'],
               default='guests',
               help='Ver guests/hosts')

g.add_argument('--iniciar', action='store_true',
               default=argparse.SUPPRESS,
               help='Iniciar Guest')
g.add_argument('--apagar', action='store_true',
               default=argparse.SUPPRESS,
               help='Apagar Guest')


args = p.parse_args()


def main():
    try:
        print args

        if 'host' in args:
            if args.host in config.creds.keys():
                # me quedo solo con la configuracion del host donde voy a buscar el
                # guest, para acelerar el proceso de conexion
                config.creds = {args.host: config.creds[args.host]}
            else:
                print "No existe el host %s en la config" % args.host
                exit(1)

        a = Administrador(config)

        if 'ver' in args:
            for h in a.hosts.values():
                print h
                if args.ver == "guests":
                    for g in h.guests.values():
                        print "\t", g
        elif 'iniciar' in args:
            a.iniciarGuest(args.guest, args.host)
        elif 'apagar' in apagar:
            a.apagarGuest(args.guest, args.host)

        if 'interactivo' in args:
            embed()
            exit(0)

    except Exception:
        print_exc(file=stdout)
        exit(1)


if __name__ == "__main__":
    main()
