import unittest
import sys
import os
import subprocess
import zlib
import base64
import hashlib

from studio import studiologging as sl
from studio.runner import LocalExecutor

class RunnerTest(unittest.TestCase):
    def test_LocalExecutor_run(self):
        executor = LocalExecutor()
        my_path = os.path.dirname(os.path.realpath(__file__))
        os.chdir(my_path)

        test_script = 'tf_hello_world.py'
        experiment_name = 'experimentHelloWorld' 
        executor.db.delete('experiments/' + experiment_name)
        executor.run(test_script, [], experiment_name = experiment_name, save_workspace=True)
 
        # test saved arguments
        saved_args = executor.db['experiments/' + experiment_name + '/args']
        self.assertTrue(len(saved_args) == 1)
        self.assertTrue(saved_args[0] == test_script)

        # test saved stdout
        modelDir = executor.db['experiments/' + experiment_name + '/modeldir']
        for k in modelDir.keys():
            if modelDir[k]['name'] == 'output.log':
                data = zlib.decompress(base64.b64decode(modelDir[k]['data']))
                self.assertTrue(k == hashlib.sha256(data).hexdigest())

                splitData = data.strip().split('\n')
                self.assertEquals(splitData[-1],'[ 2.  6.]')

        
        self.check_workspace(executor.db, 'experiments/' + experiment_name + '/workspace/')
        self.check_workspace(executor.db, 'experiments/' + experiment_name + '/workspace_latest/')


    def check_workspace(self, db, keyBase):
        dbFiles = db[keyBase]
        savedFiles = []
        for k in dbFiles.keys():
            savedData = zlib.decompress(base64.b64decode(dbFiles[k]['data']))
            self.assertTrue(k == hashlib.sha256(savedData).hexdigest())
            savedName = dbFiles[k]['name']
            with open(savedName, 'rb') as f:
                localData = f.read()
                self.assertEquals(localData, savedData)
            savedFiles.append(savedName)
        
        savedFilesSet = set(savedFiles)
        localFilesSet = set(os.listdir('.'))

        self.assertTrue(len(savedFilesSet) == len(savedFilesSet | localFilesSet))


       

if __name__ == "__main__":
    unittest.main()

