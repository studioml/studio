import uuid
import unittest
import os
from completion_service import CompletionService


class CompletionServiceTest(unittest.TestCase):

    def test_two_experiments(self):
        experimentId = str(uuid.uuid4())
        config_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            '..', 'studio', 'tests', 'test_config.yaml')

        with CompletionService(experimentId, config=config_path) as cs:
            e1 = cs.submitTask('./completion_service_func.py', [1])
            e2 = cs.submitTask('./completion_service_func.py', [2])

            results = cs.getResults(blocking=True)

        expected_results = {e1: [1], e2: [2]}
        self.assertEquals(results, expected_results)


if __name__ == '__main__':
    unittest.main()
