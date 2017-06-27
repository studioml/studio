import unittest
from studio import util


class UtilTest(unittest.TestCase):
    def test_remove_backspaces(self):
        testline = 'abcd\x08\x08\x08efg\x08\x08hi\x08'
        removed = util.remove_backspaces(testline)
        self.assertTrue(removed == 'aeh')

        testline = 'abcd\x08\x08\x08efg\x08\x08hi'
        removed = util.remove_backspaces(testline)
        self.assertTrue(removed == 'aehi')

        testline = 'abcd'
        removed = util.remove_backspaces(testline)
        self.assertTrue(removed == 'abcd')

        testline = 'abcd\n\ndef'
        removed = util.remove_backspaces(testline)
        self.assertTrue(removed == testline)


if __name__ == "__main__":
    unittest.main()
