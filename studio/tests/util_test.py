import unittest
from studio import util
from random import randint


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

    def test_retry(self):
        attempts = [0]
        value = randint(0, 1000)

        def failing_func():
            attempts[0] += 1
            if attempts[0] != 2:
                raise ValueError('Attempt {} failed'
                                 .format(attempts[0]))
            return value

        retval = util.retry(failing_func,
                            no_retries=2,
                            sleep_time=1,
                            exception_class=ValueError)

        self.assertEquals(retval, value)
        self.assertEquals(attempts, [2])

        # test out for catching different exception class
        try:
            retval = util.retry(failing_func,
                                no_retries=2,
                                sleep_time=1,
                                exception_class=OSError)
        except ValueError:
            pass
        else:
            self.assertTrue(False)

    def test_str2duration(self):
        self.assertEqual(
            int(util.str2duration('30m').total_seconds()),
            1800)


if __name__ == "__main__":
    unittest.main()
