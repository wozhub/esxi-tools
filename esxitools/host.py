#!/usr/bin/python

from sh import sshpass, ssh
from pysphere import VIServer
from datetime import datetime, timedelta

from queues import Copia, CopyQueue


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

        self.dsa_key = False

        # manejo el objeto ssh
        self._ssh_updated = datetime.now()
        self._ssh = self._ssh()

        # manejo el objeto pysphere
        self._esxi_updated = datetime.now()
        self._esxi = self.conexion_viserver()

        if configurarGuests:
            self._configurarGuests()

        ssh = self.conexion_ssh()
        ssh.ln("-sf", "`which vim-cmd`", "/bin/vim_cmd")
        try:
            ssh.vim_cmd("hostsvc/firewall_enable_ruleset", "sshClient")
        except:
            pass

    def _configurarGuests(self):
        self.logger.debug(self)
        self.guests = {}

        for path in self.esxi.get_registered_vms():
            esxi = self.esxi.get_vm_by_path(path)
            vm = esxi.get_property('name')
            self.logger.debug("Encontre a %s en %s", vm, self)
            self.guests[vm] = Guest(self, vm, esxi)

    @property
    def ssh(self):
        if self._ssh_updated + timedelta(seconds=30) < datetime.now():
            try:
                self.ssh.test()
            except:
                self._ssh = self._ssh()
            self._ssh_updated = datetime.now()
        return self._ssh

    @property
    def esxi(self):
        if self._esxi_updated + timedelta(seconds=30) < datetime.now():
            try:
                self.esxi.get_api_version()
            except:
                self._esxi = self.conexion_viserver()
            self._esxi_updated = datetime.now()
        return self._esxi

    def __repr__(self):
        return "%s (%s @ %s)" % (self.name, self.__class__, self.creds['ip'])

    def instalarDSA(self, dsa_key):
        if self.dsa_key is True:
            return

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

        self.dsa_key = True

    def buscarGuest(self, nombre):
        for g in self.guests.values():
            if g.name == nombre:
                return g

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
        login = self.creds['user']+"@"+self.creds['ip']

        if self.dsa_key is False:
            sp = self._sshpass()
            conexion = sp.bake("ssh", login)
        else:
            conexion = ssh.bake(login)
        return conexion

    def _sshpass(self):
        s = sshpass.bake("-p", self.creds['pw'])
        return s


