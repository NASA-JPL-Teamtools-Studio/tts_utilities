import ipynbname
from pathlib import Path

def this_notebook_path():
    try:
        return Path(ipynbname.path())
    except AttributeError:
        raise Exception('Not running in a Jupyter notebook')

def this_notebook_name():
    try:
        return ipynbname.name()
    except AttributeError:
        raise Exception('Not running in a Jupyter notebook')
        return None
