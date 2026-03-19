#Helper file to support installing locally on older Python systems
#once we can move 100% to a system like pyproject.toml or poetry
#we can ditch this file and setup_from_pyproject. But as long
#as we have missions on 3.6.4, we should keep it in place so
#we can dev locally on those projects and install this locally
import os
import sys

# Add src/ to sys.path so the package can be found.
# this is a special need for tts-deployments only. 
# don't copy this line into other repos. Those other repos
# require tts-deployments as a build dependency, but 
# tts-deployments can't require itself, so we have to 
# import it locally like this at build time.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from tts_utilities.setup_from_pyproject import setup_from_pyproject
setup_from_pyproject()
