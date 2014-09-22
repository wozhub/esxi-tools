#!/usr/bin/python

from sh import sshpass
from pysphere import VIServer

from queues import Copia, CopyQueue, CompressQueue
from utiles import obtenerLogger


class Configuracion:
    def __init__(self, config):
        self.config = config
        self.backup_folder = config['backup_folder']
        self.creds = config['creds']
        self.logfile = config['log_esxitools']
        self.logpysphere = config['log_pysphere']

    def buscarCredenciales(self, host):
        return self.creds[host]


class Administrador:
    def __init__(self, config):
        self.config = config

        self.logger = obtenerLogger(self.config.logfile)
        self.logger.debug('Creando Administrador')

        self.fila_compresion = CompressQueue(self)

        self._configurarHosts()

    def _configurarHosts(self):
        self.logger.debug('')
        self.hosts = []
        for host in self.config.creds:
            self.hosts.append(Host(self, host))


class Host:
    def __init__(self, admin, host):
        self.admin = admin
        self.name = host
        self.config = self.admin.config
        self.logger = self.admin.logger
        self.logger.debug('Creando Host')

        self.creds = self.config.buscarCredenciales(host)
        self.fila_copia = CopyQueue(self)
        self.fila_compresion = self.admin.fila_compresion

        self._configurarGuests()

    def _configurarGuests(self):
        self.logger.debug(self)
        self.guests = []
        esxi = self.conexion_viserver()

        for path in esxi.get_registered_vms():
            vm = esxi.get_vm_by_path(path).get_property('name')
            self.logger.debug("Encontre a %s en %s", vm, self)
            self.guests.append(Guest(self, vm))

    def __repr__(self):
        return "%s (%s)" % (self.name, self.__class__)

    def conexion_viserver(self):
        self.logger.debug(self)
        esxi = VIServer()
        esxi.connect(self.creds['ip'], self.creds['user'],
                     self.creds['pw'], trace_file=self.config.logpysphere)

        self.logger.debug("Conectado a %s %s", esxi.get_server_type(),
                          esxi.get_api_version())
        return esxi

    def conexion_ssh(self):
        self.logger.debug(self)
        sp = self._sshpass()
        login = self.creds['user']+"@"+self.creds['ip']
        ssh = sp.bake("ssh", login)
        return ssh

    def _sshpass(self):
        s = sshpass.bake("-p", self.creds['pw'])
        return s


class Guest:
    def __init__(self, host, guest):
        self.host = host
        self.name = guest
        self.logger = self.host.logger
        self.logger.debug('Creando Guest (%s)', self.name)
        self.backup_folder = host.config.backup_folder + '/' + self.name

        self._obtenerRuta()
        self._obtenerArchivos()

    def __repr__(self):
        return "%s (%s)" % (self.name, self.__class__)

    def tieneTools(self):
        esxi = self.host.conexion_viserver()
        for path in esxi.get_registered_vms():
            if esxi.get_vm_by_path(path).get_property('name') == self.name:
                if esxi.get_vm_by_path(path).get_property('ip_address'):
                    return 1
                else:
                    return 0

    def tieneSnapshots(self):
        esxi = self.host.conexion_viserver()
        for path in esxi.get_registered_vms():
            if esxi.get_vm_by_path(path).get_property('name') == self.name:
                if esxi.get_vm_by_path(path).get_snapshots():
                    return 1
                else:
                    return 0

    def reiniciar(self):
        esxi = self.host.conexion_viserver()
        for path in esxi.get_registered_vms():
            if esxi.get_vm_by_path(path).get_property('name') == self.name:
                esxi.get_vm_by_path(path).reset()

    def respaldar(self):
        self.logger.debug(self)

        c = Copia(self.host, self)
        self.host.fila_copia.cargar(c)
        self.host.fila_copia.procesar()
        self.host.fila_compresion.procesar()

    def crearSnapshot(self, desc):
        esxi = self.host.conexion_viserver()
        for path in esxi.get_registered_vms():
            if self.name == esxi.get_vm_by_path(path).get_property('name'):
                esxi.get_vm_by_path(path).create_snapshot(desc, sync_run=True)

    def borrarSnapshot(self, desc):
        esxi = self.host.conexion_viserver()
        for path in esxi.get_registered_vms():
            if self.name == esxi.get_vm_by_path(path).get_property('name'):
                esxi.get_vm_by_path(path).delete_named_snapshot(desc,
                                                                sync_run=False)

    def _obtenerArchivos(self):
        archivos = []
        ssh = self.host.conexion_ssh()
        for archivo in ssh.ls(self.ruta).splitlines():
            if "~" in archivo or "vswp" in archivo \
                    or "lck" in archivo or "log" in archivo:
                continue
            archivos.append(archivo)
        self.archivos = archivos

    def _obtenerRuta(self):
        esxi = self.host.conexion_viserver()
        for path in esxi.get_registered_vms():
            if self.name == esxi.get_vm_by_path(path).get_property('name'):
                r = ""
                ruta = esxi.get_vm_by_path(path).get_property('path')
                for palabra in ruta.split():
                    if "datastore1" in palabra:
                        r = "/vmfs/volumes/datastore1/"
                    else:
                        for carpeta in palabra.split('/'):
                            if "vmx" not in carpeta:
                                r += carpeta
        self.ruta = r
