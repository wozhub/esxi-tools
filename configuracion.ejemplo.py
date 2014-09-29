#!/usr/bin/python

from clases import Configuracion

config = Configuracion({
    'log_pysphere': '/tmp/pysphere.log',
    'log_esxitools': '/tmp/esxi-tools.log',
    'backup_folder': '/tmp',
    'creds': {'servidor1': {'user': 'root',
                            'pw': 'clave',
                            'ip': 'ip'},
              'servidor2': {'user': 'root',
                            'pw': 'clave',
                            'ip': 'ip'},
              }
    })

