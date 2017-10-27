import unittest
import tempfile
import os
import subprocess
import uuid
import re
from studio import git_util


class GitUtilTest(unittest.TestCase):

    def test_is_git(self):
        self.assertTrue(git_util.is_git())

    def test_is_not_git(self):
        self.assertFalse(git_util.is_git(tempfile.gettempdir()))

    def test_is_not_clean(self):
        filename = str(uuid.uuid4())
        subprocess.call(['touch', filename])
        is_clean = git_util.is_clean()
        os.remove(filename)
        self.assertFalse(is_clean)

    @unittest.skipIf(os.environ.get('TEST_GIT_REPO_ADDRESS') != 1,
                     'skip if being tested from a forked repo')
    def test_repo_url(self):
        expected = re.compile(
            'https{0,1}://github\.com/studioml/studio(\.git){0,1}')
        expected2 = re.compile(
            'git@github\.com:studioml/studio(\.git){0,1}')
        actual = git_util.get_repo_url(remove_user=True)
        self.assertTrue(
            (expected.match(actual) is not None) or
            (expected2.match(actual) is not None))


if __name__ == "__main__":
    unittest.main()
