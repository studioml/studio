import os
import subprocess
import uuid

from studio import runner

class CompletionService:

    def __init__(self, config=None, resources_needed=None, cloud=None):
        self.config = config    
        self.resources_needed = resources_needed
        self.wm = runner.get_worker_manager(config, cloud)

    def submitTask(experimentId, clientCodeFile, args):
        project_name = "completion_service_" + experimentId
        queue_name = project_name
        cwd = os.path.dirname(os.path.realpath(__file__)),
          
        artifacts = {
            'retval': {
                'mutable':True,
                'local':'./retval.pkl'
            }
            'clientscript': {
                'mutable': False,
                'local': clientCodeFile
            }
        }

        experiment_name = project_name + "_" + str(uuid.uuid4())   
        experiment = model.create_experiment(
            'completion_service_client.py'
            args,
            experiment_name=experiment_name
            project=project_name,
            artifacts=artifacts,
            resources_needed=self.resources_needed)

        with model.get_db_provider(self.config) as db:
            db.add_experiment(experiment)
            runner.submit_experiment()

        return experiment_name              
              
            
    def submitTaskWithFiles():
        raise NotImplementedError

    def getResults():
        raise NotImplementedError

    def getResultsWithTimeout():
        raise NotImplementedError

