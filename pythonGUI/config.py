import yaml
from box import Box
import sys
import os

currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
configdir = os.path.join(currentdir, 'configs')
if not os.path.exists(configdir):
    configdir = os.path.join(parentdir, 'configs')
    if not os.path.exists(configdir):
        raise FileNotFoundError(f"No configs directory found")

with open(os.path.join(configdir,"config.yml"), "r") as ymlfile:
    cfg = Box(yaml.safe_load(ymlfile))