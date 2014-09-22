#!/usr/bin/python

from logging import getLogger, Formatter, FileHandler, StreamHandler
from logging import INFO, DEBUG, ERROR

from os import makedirs, remove
import errno


def borrarArchivo(archivo):
    try:
        remove(archivo)
    except OSError, e:  ## if failed, report it back to the user ##
        print ("Error: %s - %s." % (e.filename,e.strerror))


def verificarDirectorio(path):
    try:
        makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise


def obtenerLogger(output):
    logger = getLogger('esxi-tools')
    logger.setLevel(DEBUG)

    formato = Formatter('%(asctime)s\t%(levelname)s\t%(module)s\t%(funcName)s\t%(message)s',
                        "%Y-%m-%d %H:%M:%S")

    fh = FileHandler(output)
    fh.setLevel(DEBUG)
    fh.setFormatter(formato)

    ch = StreamHandler()
    ch.setLevel(INFO)
    ch.setFormatter(formato)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger
