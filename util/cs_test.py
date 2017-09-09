import uuid
from completion_service import CompletionService

experimentId = str(uuid.uuid4())
with CompletionService(experimentId) as cs:
    cs.submitTask('./completion_service_test.py', [])



