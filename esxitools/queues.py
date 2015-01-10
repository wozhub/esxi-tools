#!/usr/bin/python

from Queue import Queue
from threading import Thread
from time import time
from gzip import open as gzip
from os import listdir
from datetime import datetime

from utiles import verificarDirectorio, borrarArchivo


class Copia:
    def __init__(self, host, guest):
        self.h = host
        self.g = guest
        self.f = "%s" % datetime.now().strftime('%y-%m-%d')
        self.archivos = guest.archivos
        self.origen = guest.ruta
        self.destino = guest.backup_folder + '/' + self.f

    def __repr__(self):
        return "%s %s (%s)" % (self.h, self.g, self.__class__)


class CopyQueue:
    def __init__(self, parent):
        self.host = parent
        self.logger = self.host.logger
        self.logger.debug('Iniciando CopyQueue')

        self.aCopiar = Queue()

        self.worker = Thread(target=self.copiar, args=(0,))
        self.worker.setDaemon(True)
        self.worker.start()

    def procesar(self):
        self.aCopiar.join()

    def cargar(self, copia):
        self.logger.info("Cargando %s en la fila de copia" % copia.g)
        self.aCopiar.put(copia)

    def copiar(self, i):
        while True:
            copia = self.aCopiar.get()

            if copia:

                if copia.g.tieneSnapshots:
                    log = '%s: %s Ya tiene Snapshots!' % (copia.h, copia.g)
                    self.logger.error(log)

                    self.aCopiar.task_done()

                else:
                    if not copia.g.tieneTools:
                        log = '%s: %s No tiene Vmware Tools!' % (copia.h,
                                                                 copia.g)
                        self.logger.warning(log)

                    log = '%s: Copiando %s a %s' % (copia.h, copia.g,
                                                    copia.destino)
                    self.logger.info(log)

                    log = "%s -> %s %s " % (copia.origen, copia.destino,
                                            copia.archivos)
                    self.logger.info(log)

                    verificarDirectorio(copia.destino)

                    copia.g.crearSnapshot("respaldo")

                    ssh = copia.h.conexion_ssh()

                    try:
                        for archivo in copia.g.archivos:
                            # print ssh.grep(ssh.lsof(),archivo)
                            peso = ssh.du(copia.origen+'/'+archivo)
                            peso = int(str(peso).split('\t')[0])/1024

                            log = "%s: %s: %s [%s mb]" % (copia.h, copia.g,
                                                          archivo, peso)
                            self.logger.info(log)

                            inicio = time()
                            sshpass = copia.h._sshpass()
                            arg = "%s@%s:%s/%s" % (copia.h.creds['user'],
                                                   copia.h.creds['ip'],
                                                   copia.origen, archivo)

                            sshpass.scp("-o Cipher=blowfish-cbc", arg,
                                        copia.destino)

                            fin = time()
                            delta = round(fin-inicio)+1
                            velocidad = peso/delta

                            log = "%s: %s: %s [%s mb/s]" % (copia.h, copia.g,
                                                            archivo, velocidad)
                            self.logger.warn(log)

                    except Exception as e:
                        self.logger.error(e)
                        raise
                    else:
                        copia.h.fila_compresion.cargar(copia)
                        copia.g.borrarSnapshot("respaldo")
                    finally:
                        self.aCopiar.task_done()


class CompressQueue:
    def __init__(self, parent):
        self.admin = parent
        self.logger = self.admin.logger
        self.logger.debug('Iniciando CompressQueue')

        self.aComprimir = Queue()

        self.worker = Thread(target=self.comprimir, args=(0,))
        self.worker.setDaemon(True)
        self.worker.start()

    def cargar(self, copia):
        log = "Cargando %s en la pila de compresion" % copia
        self.logger.info(log)
        self.aComprimir.put(copia)

    def comprimir(self, i):
        while True:
            copia = self.aComprimir.get()

            if copia:
                destino = copia.destino

                log = "%s: Comprimiendo archivos en %s" % (copia.g,
                                                           copia.destino)
                self.logger.warn(log)
                archivos = listdir(destino)

                self.logger.debug(archivos)

                for archivo in archivos:
                    try:
                        log = '%s: %s: Comprimiendo.' % (copia.g, archivo)
                        self.logger.info(log)

                        a = destino+'/'+archivo
                        f_in = open(a, 'rb')
                        f_out = gzip(a+'.gz', 'wb')
                        f_out.writelines(f_in)
                        f_out.close()
                        f_in.close()
                    except Exception as e:
                        log = '%s: %s: Error al comprimir: %s' % (copia.g,
                                                                  archivo, e)
                        self.logger.error(log)
                    else:
                        log = '%s: %s: Compresion completa.' % (copia.g,
                                                                archivo)
                        self.logger.warn(log)
                        borrarArchivo(a)

                self.aComprimir.task_done()

    def procesar(self):
        self.aComprimir.join()
