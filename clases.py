#!/usr/bin/python

from sh import sshpass
from pysphere import VIServer
from time import time

from queues import Copia, CopyQueue, CompressQueue
from utiles import obtenerLogger

from datetime import datetime, timedelta

class Configuracion:
    def __init__(self, config):
        self.config = config
        self.backup_folder = config['backup_folder']
        self.creds = config['creds']
        self.logfile = config['log_esxitools']
        self.logpysphere = config['log_pysphere']
        self.dsa_key = config['dsa_key']
        self.dsa_key_priv = config['dsa_key_priv']

    def buscarCredenciales(self, host):
        return self.creds[host]


class Administrador:
    def __init__(self, config, configurarGuests=True):
        self.config = config
        self.logger = obtenerLogger(self.config.logfile)
        self.logger.debug('Creando Administrador')
        self.fila_compresion = CompressQueue(self)
        self.filas_copia = []

        self._configurarHosts(configurarGuests=configurarGuests)

    def _configurarHosts(self, configurarGuests):
        self.logger.debug('')
        self.hosts = []
        for host in self.config.creds:
            self.hosts.append(Host(self, host, configurarGuests))

        # instalo la key para conectarme sin password
        for host in self.hosts:
            host.instalarDSA(self.config.dsa_key)

    def respaldar(self):
        self.logger.debug(self)

        for h in self.hosts:
            for g in h.guests:
                c = Copia(self, g)
                h.fila_copia.cargar(c)

        for h in self.hosts:
            h.fila_copia.procesar()

        self.fila_compresion.procesar()

    def buscarGuest(self, nombre):
        for h in self.hosts:
            for g in h.guests:
                if g.name == nombre:
                    return g

    def buscarHost(self, nombre):
        for h in self.hosts:
            if h.name == nombre:
                return h

    def migrar(self, nombre_vm, host_destino):
        g_o = self.buscarGuest(nombre_vm)
        h_o = g_o.host
        h_d = self.buscarHost(host_destino)

        estado = g_o.estado()
        if estado == 'POWERED ON':  # apaga la vm en origen
            g_o.apagar(sync_run=True)

        ssh = h_o.conexion_ssh()
        ssh.echo("'%s'" % h_o.config.dsa_key_priv, ">", "/tmp/identidad")

        # copia los archivos
        arg = "%s@%s:%s" % (h_d.creds['user'], h_d.creds['ip'], g_o.ruta)
        # print ssh.scp("-i /tmp/identidad", "-o UserKnownHostsFile=/dev/null",
        #              "-o StrictHostKeyChecking=no", "-r", g_o.ruta, arg)

        ssh_dest = h_d.conexion_ssh()
        for archivo in g_o.archivos:  # agrega la vm al inventario destino
            if ".vmx" in archivo:
                vmx = "%s/%s" % (g_o.ruta, archivo)
                print ssh_dest.vim_cmd("solo/registervm", vmx)
                break

        h_d._configurarGuests(self)  # vuelvo a buscar g en destino
        g_d = self.buscarGuest(nombre_vm)

        if estado == 'POWERED ON':  # enciende la vm en destino
            g_d.apagar(sync_run=True)

        # quita la vm del inventario origen

        # cambia el nombre de la carpeta de la vm en origen


class Host:
    def __init__(self, admin, host, configurarGuests=True):
        self.admin = admin
        self.name = host
        self.config = self.admin.config
        self.logger = self.admin.logger
        self.logger.debug('Creando Host')

        self.creds = self.config.buscarCredenciales(host)
        self.fila_copia = CopyQueue(self)
        self.admin.filas_copia.append(self.fila_copia)
        self.fila_compresion = self.admin.fila_compresion

        # manejo el objeto pysphere
        self._esxi_updated = datetime.now()
        self._esxi = self.conexion_viserver()

        if configurarGuests:
            self._configurarGuests()

        ssh = self.conexion_ssh()
        ssh.ln("-sf", "`which vim-cmd`", "/bin/vim_cmd")
        ssh.vim_cmd("hostsvc/firewall_enable_ruleset", "sshClient")


    def _configurarGuests(self):
        self.logger.debug(self)
        self.guests = []

        for path in self.esxi.get_registered_vms():
            esxi = self.esxi.get_vm_by_path(path)
            vm = esxi.get_property('name')
            self.logger.debug("Encontre a %s en %s", vm, self)
            self.guests.append(Guest(self, vm, esxi))

    @property
    def esxi(self):
        if self._esxi_updated + timedelta(seconds=30) < datetime.now():
            print "Reconectando"
            self._esxi_updated = datetime.now()
            self._esxi = self.conexion_viserver()
        return self._esxi

    def __repr__(self):
        return "%s (%s)" % (self.name, self.__class__)

    def instalarDSA(self, dsa_key):
        version = self.esxi.get_api_version()
        ssh = self.conexion_ssh()

        if version in ["4.1", ]:  # Versiones anteriores a la 5
            try: ssh.mkdir("~/.ssh")
            except: pass
            archivo = "~/.ssh/authorized_keys"
            ssh.touch(archivo)
        else:
            archivo = "/etc/ssh/keys-root/authorized_keys"

        if "esxi-tools" not in ssh.cat(archivo):
            ssh.echo(dsa_key, ">>", archivo)

    def respaldar(self):
        self.logger.debug(self)

        for g in self.guests:
            c = Copia(self, g)
            self.fila_copia.cargar(c)

        self.fila_copia.procesar()
        self.fila_compresion.procesar()

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
    def __init__(self, host, guest, esxi):
        self.host = host
        self.name = guest
        self.logger = self.host.logger
        self.logger.debug('Creando Guest (%s)', self.name)
        self.backup_folder = host.config.backup_folder + '/' + self.name

        self._obtenerRuta()
        self._obtenerArchivos()

        # manejo el objeto pysphere
        self._esxi_updated = datetime.now()
        self._esxi = esxi

    def __repr__(self):
        return "%s (%s)" % (self.name, self.__class__)

    @property
    def esxi(self):
        if self._esxi_updated + timedelta(seconds=30) < datetime.now():
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
