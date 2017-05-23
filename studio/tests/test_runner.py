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
        myPath = os.path.dirname(os.path.realpath(__file__))
        os.chdir(myPath)

        testScript = 'tf_hello_world.py'
        experimentName = 'experimentHelloWorld' 
        executor.db.delete('experiments/' + experimentName)
        executor.run(testScript, [], experimentName, saveWorkspace=True)
 
        # test saved arguments
        savedArgs = executor.db['experiments/' + experimentName + '/args']
        self.assertTrue(len(savedArgs) == 1)
        self.assertTrue(savedArgs[0] == testScript)

        # test saved stdout
        modelDir = executor.db['experiments/' + experimentName + '/modeldir']
        for k in modelDir.keys():
            if modelDir[k]['name'] == 'output.log':
                data = zlib.decompress(base64.b64decode(modelDir[k]['data']))
                self.assertTrue(k == hashlib.sha256(data).hexdigest())

                splitData = data.strip().split('\n')
                self.assertEquals(splitData[-1],'[ 2.  6.]')

        
        self.checkWorkspace(executor.db, 'experiments/' + experimentName + '/workspace/')
        self.checkWorkspace(executor.db, 'experiments/' + experimentName + '/workspace_latest/')


    def checkWorkspace(self, db, keyBase):
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

