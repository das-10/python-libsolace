__author__ = 'johlyh'
__yamlfiles__ = [
    'libsolace.yaml',
    '/etc/libsolace/libsolace.yaml',
    '/opt/libsolace/libsolace.yaml'
]
__doc__ = """

>>> import libsolace.settingsloader as settings
>>> settings.CMDB_URL
"http://mydomain.com/path"
"""

import yaml
import os
import logging
import sys
logging.basicConfig(format='[%(module)s] %(filename)s:%(lineno)s %(asctime)s %(levelname)s %(message)s',stream=sys.stdout)
logging.getLogger().setLevel(logging.INFO)

logging = logging.getLogger(__name__)
yaml_loaded = False

# defaults which are set / could not be present
defaults = {
    "UPDATE_MOCK_TESTS": False,
    "CMDB_URL": "http://someurl/site.xml",
    "CMDB_FILE": "provision-example.yaml",
    "CMDB_USER": "",
    "CMDB_PASS": ""
}

for yaml_file in __yamlfiles__:
    if not os.path.exists(yaml_file):
        continue
    logging.info("Using yaml file %s" % yaml_file)
    stream = open(yaml_file, 'r')
    yaml_settings = yaml.load(stream)

    # set the defaults
    for default in defaults:
        logging.info("Setting default %s:%s" % (default, defaults[default]))
        globals()[default] = defaults[default]

    # TODO FIXME
    # get each plugins "default" variables and add to globals

    # get the real values if any
    for variable in yaml_settings.keys():
        logging.info("Setting config %s:%s" % (variable, yaml_settings[variable]))
        globals()[variable] = yaml_settings[variable]

    yaml_loaded = True
    logging.debug("Yaml loaded successful")

    logging.info("Loading plugins...")
    for p in globals()['PLUGINS']:
        try:
            __import__(p, globals())
        except Exception, e:
            logging.error("Failed to import plugin %s" % p)
            raise
    break

if yaml_loaded is False:
    msg = "Failed to find libpipeline.yaml in any of these locations: %s" % ",".join(__yamlfiles__)
    logging.error(msg)
    raise Exception(msg)