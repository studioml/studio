import unittest
import subprocess
import time

from random import randint
from threading import Thread
from multiprocessing import Process
from subprocess import Popen

from studio import model
from studio import studio
from model_test import get_test_experiment

class HTTPProviderTest(unittest.TestCase):
 
    @classmethod   
    def setUpClass(self):
        print "Setting up"
        self.port = randint(5000, 9000)        
            
        # self.app.run(port=self.port, debug=True)
        # self.serverp.start()
                
        self.serverp = subprocess.Popen([
                'studio-ui',
                '--port=' + str(self.port),
                '--verbose=debug',
                '--config=test_config_http_server.yaml',
                '--host=localhost'])
        
        time.sleep(10)

    @classmethod
    def tearDownClass(self):      
        print "Tearing down"
        
        self.serverp.kill()

    def get_db_provider(self):
        config = model.get_config('test_config_http.yaml')
        config['database']['serverUrl'] = 'http://localhost:' + str(self.port)
        return model.get_db_provider(config)       

    def test_add_get_experiment(self):
        experiment_tuple = get_test_experiment()
        db = self.get_db_provider()
        import pdb
        pdb.set_trace()
        db.add_experiment(experiment_tuple[0])

        experiment = db.get_experiment(experiment_tuple[0].key)
        self.assertEquals(experiment.key, experiment_tuple[0].key)
        self.assertEquals(experiment.filename, experiment_tuple[0].filename)
        self.assertEquals(experiment.args, experiment_tuple[0].args)
        


if __name__ == '__main__':
    unittest.main()
