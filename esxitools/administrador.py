#!/usr/bin/python

from time import sleep

from host import Host
from guest import Guest
from queues import Copia, CompressQueue
from utiles import obtenerLogger


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
        self.hosts = {}
        for host in self.config.creds:
            try:
                h = Host(self, host, configurarGuests)
            except:
                print host
                continue

            self.hosts[host] = h

        # instalo la key para conectarme sin password
        for host in self.hosts.values():
            host.instalarDSA(self.config.dsa_key)

    def respaldar(self):
        self.logger.debug(self)

        for h in self.hosts.values():
            for g in h.guests.values():
                c = Copia(self, g)
                h.fila_copia.cargar(c)

        for h in self.hosts.values():
            h.fila_copia.procesar()

        self.fila_compresion.procesar()

    def buscarHost(self, nombre):
        for h in self.hosts.values():
            if h.name == nombre:
                return h

    def iniciarGuest(self, guest, host=None):
        if host is None:
            for h in self.hosts.values():
                g = h.buscarGuest(guest)
                if g:
                    g.iniciar(sync_run=True)
                    return True
        else:
            h = self.buscarHost(host)
            if h:
                g = h.buscarGuest(guest)
                if g:
                    g.iniciar(sync_run=True)

    def apagarGuest(self, guest, host=None):
        if host is None:
            for h in self.hosts.values():
                g = h.buscarGuest(guest)
                if g:
                    g.apagar(sync_run=True)
                    return True
        else:
            h = self.buscarHost(host)
            if h:
                g = h.buscarGuest(guest)
                if g:
                    g.apagar(sync_run=True)

    def migrar(self, vm, origen, destino):
        g_o = self.hosts[origen].guests[vm]
        h_o = self.hosts[origen]
        h_d = self.hosts[destino]

        estado = g_o.estado
        if estado == 'POWERED ON':  # apaga la vm en origen
            self.logger.debug("%s esta encendida.", vm)
            g_o.apagar(sync_run=True)

        ssh_origen = h_o.conexion_ssh()
        for linea in ssh_origen.vim_cmd("vmsvc/getallvms"):
            if vm in linea:
                id_o = linea.split()[0]

        self.logger.debug("Copiando archivo de identidad dsa.")
        ssh_origen.echo("'%s'" % h_o.config.dsa_key_priv, ">", "/tmp/identidad")
        ssh_origen.chmod("700", "/tmp/identidad")

        self.logger.debug("Copiando archivos de la vm.")
        arg = "%s@%s:%s" % (h_d.creds['user'], h_d.creds['ip'], g_o.ruta)
        #ssh_origen.scp("-i /tmp/identidad", "-o UserKnownHostsFile=/dev/null",
        ssh_origen.scp("-i /tmp/identidad",
                       "-o StrictHostKeyChecking=no", "-r", g_o.ruta, arg)

        self.logger.debug("Agregando vm al inventario destino.")
        ssh_dest = h_d.conexion_ssh()
        for archivo in g_o.archivos:  # agrega la vm al inventario destino
            if ".vmx" in archivo:
                vmx = "%s/%s" % (g_o.ruta, archivo)
                ssh_dest.vim_cmd("solo/registervm", vmx)
                break

        h_d._configurarGuests()  # vuelvo a buscar g en destino
        g_d = self.hosts[destino].guests[vm]

        if estado == 'POWERED ON':  # enciende la vm en destino
            self.logger.debug("Encendiendo la vm en el host destino.")
            g_d.iniciar(sync_run=False)
            sleep(2)
            pregunta = g_d.esxi.get_question()
            for respuesta in pregunta.choices():
                    if "moved" in respuesta[1]:
                                break
            pregunta.answer(respuesta[0])

        self.logger.debug("Quitando del inventario origen")
        ssh_origen.vim_cmd("vmsvc/unregister", id_o)
        self.logger.debug("Cambiando de nombre a la carpeta en origen")
        ssh_origen.mv(g_o.ruta, g_o.ruta+"_migrada")


