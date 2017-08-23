import unittest
import subprocess
import time

from studio import model
from model_test import get_test_experiment

class HTTPProviderTest(unittest.TestCase):
 
    @classmethod   
    def setUpClass(self):
        print "Setting up"
        self.serverp = subprocess.Popen(['studio','ui', '--port=5123'])
        time.sleep(10)

    @classmethod
    def tearDownClass(self):      
        print "Tearing down"
        #self.serverp.kill()

    def get_db_provider(self):
        return model.get_db_provider(model.get_config('test_config_http.yaml'))       

    def test_add_get_experiment(self):
        db = self.get_db_provider()
        experiment_tuple = get_test_experiment()
        db.add_experiment(experiment_tuple[0])

        experiment = db.get_experiment(experiment_tuple[0].key)
        self.assertEquals(experiment.key, experiment_tuple[0].key)
        self.assertEquals(experiment.filename, experiment_tuple[0].filename)
        self.assertEquals(experiment.args, experiment_tuple[0].args)
        
        


if __name__ == '__main__':
    unittest.main()
