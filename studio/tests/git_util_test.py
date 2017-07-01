import unittest
import tempfile
import os
import subprocess
import uuid
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

    def test_repo_url(self):
        expected_url1 = 'https://github.com/ilblackdragon/studio'
        expected_url1 = 'http://github.com/ilblackdragon/studio'
        actual_url = git_util.get_repo_url(remove_user=True)
        self.assertTrue(actual_url == expected_url1 or
                        actual_url == expected_url2)


if __name__ == "__main__":
    unittest.main()
