#!/usr/bin/python

import os
import sys
import subprocess
import model
import argparse
import uuid
import yaml
import hashlib

from configparser import ConfigParser

class LocalExecutor(object):
    """Runs job while capturing environment and logging results.

    TODO: capturing state and results.
    """

    def __init__(self, configFile=None):
        if configFile:
            with open(configFile) as f:
                self.config = yaml.load(f)
        else:
            self.config = self.getDefaultConfig()

        self.db = self.getDbProvider()

    def run(self, filename, args):
        experimentName = self.getUniqueExperimentName() 
        print "Experiment name: " + experimentName

        keyBase = 'experiments/' + experimentName + '/'
        self.db[keyBase + 'args'] = args 
        self.saveWorkspace(keyBase)
               
        subprocess.call(["python", filename] + args)

    def getUniqueExperimentName(self):
        return str(uuid.uuid4())

    def getDbProvider(self):
        assert 'database' in self.config.keys()
        dbConfig = self.config['database']
        assert dbConfig['type'].lower() == 'firebase'.lower()
        return model.FirebaseProvider(dbConfig['url'], dbConfig['secret'])

    def saveWorkspace(self, keyBase):
        for root, dirs, files in os.walk(".", topdown=False):
            for name in files:
                fullFileName = os.path.join(root, name)
                print("Saving " + fullFileName)
                with open(fullFileName) as f:
                    data = f.read()
                    sha = hashlib.sha256(data).hexdigest()
                    self.db[keyBase + "workspace/" + sha + "/data"] = data
                    self.db[keyBase + "workspace/" + sha + "/name"] = name

    def getDefaultConfig(self):
        return {'database': {'type':'firebase', 'url':'https://studio-ed756.firebaseio.com/', 'secret':'3NE3ONN9CJgjqhC5Ijlr9DTNXmmyladvKhD2AbLk'}}






def main(args):
    
    if len(args.script_args) < 2:
        print("Usage: studio-runner myfile.py <args>")
        return

    exec_filename, other_args = args.script_args[0], args.script_args[1:]
    # TODO: Queue the job based on arguments and only then execute.
    LocalExecutor(args.config).run(exec_filename, other_args)
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='TensorFlow Studio runner')
    parser.add_argument('script_args', metavar='N', type=str, nargs='+')
    parser.add_argument('--config', '-c', help='configuration file')



    args = parser.parse_args()
    main(args)
