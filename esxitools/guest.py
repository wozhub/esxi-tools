#!/usr/bin/python

from datetime import datetime, timedelta
from queues import Copia


class Guest:
    def __init__(self, host, guest, esxi):
        self.host = host
        self.name = guest
        self.logger = self.host.logger
        self.logger.debug('Creando Guest (%s)', self.name)
        self.backup_folder = host.config.backup_folder + '/' + self.name

        # manejo el objeto pysphere
        self._esxi_updated = datetime.now()
        self._esxi = esxi

        self.ssh = self.host.ssh

        self._obtenerRuta()
        self._obtenerArchivos()

    def __repr__(self):
        ip = self.esxi.get_property('ip_address')
        if ip:
            return "%s (%s) [%s] @ %s " % (self.name, self.__class__,
                                           self.estado, ip)
        else:
            return "%s (%s) [%s] " % (self.name, self.__class__, self.estado)

    @property
    def esxi(self):
        if self._esxi_updated + timedelta(seconds=60) < datetime.now():
            self._esxi_updated = datetime.now()
            self._esxi = self.host.esxi.get_vm_by_name(self.name)
        return self._esxi

    @property
    def estado(self):
        return self.esxi.get_status()

    @property
    def tieneTools(self):
        if self.esxi.get_property('ip_address'): return True
        else: return False

    @property
    def tieneSnapshots(self):
        if self.esxi.get_snapshots(): return True
        else: return False

    def iniciar(self, sync_run=False):
        self.esxi.power_on(sync_run=sync_run)

    def reiniciar(self, sync_run=False):
        self.esxi.reset(sync_run=sync_run)

    def apagar(self, sync_run=False):
        self.esxi.power_off(sync_run=sync_run)

    def respaldar(self):
        self.logger.debug(self)

        c = Copia(self.host, self)
        self.host.fila_copia.cargar(c)
        self.host.fila_copia.procesar()
        self.host.fila_compresion.procesar()

    def crearSnapshot(self, desc, mem=False, sync=True, qui=True):
        self.esxi.create_snapshot(desc, sync_run=sync, memory=mem, quiesce=qui)

    def borrarSnapshot(self, desc, sync=False):
        self.esxi.delete_named_snapshot(desc, sync_run=sync)

    def _obtenerArchivos(self):
        self.logger.debug(self)
        archivos = []
        for archivo in self.ssh.ls(self.ruta).splitlines():
            if "~" in archivo or "vswp" in archivo \
                    or "lck" in archivo or "log" in archivo:
                continue
            archivos.append(archivo)
        self.archivos = archivos

    def _obtenerRuta(self):
        self.logger.debug(self)
        r = ""
        ruta = self.esxi.get_property('path')
        for palabra in ruta.split():
            if "datastore1" in palabra:
                r = "/vmfs/volumes/datastore1/"
            else:
                for carpeta in palabra.split('/'):
                    if "vmx" not in carpeta:
                        r += carpeta
        self.ruta = r
