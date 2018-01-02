from google.appengine.ext import vendor
import tempfile
import subprocess

tempfile.SpooledTemporaryFile = tempfile.TemporaryFile
subprocess.Popen = None

vendor.add('lib')
