import unittest
from studio.gpu_util import memstr2int


class GpuUtilTest(unittest.TestCase):

    def test_memstr2int(self):
        self.assertEquals(memstr2int('123 Mb'), 123 * (2**20))
        self.assertEquals(memstr2int('456 MiB'), 456 * (2**20))
        self.assertEquals(memstr2int('23 Gb'), 23 * (2**30))
        self.assertEquals(memstr2int('23 GiB'), 23 * (2**30))
        self.assertEquals(memstr2int('23 '), 23)

        with self.assertRaises(ValueError):
            memstr2int('300 spartans')


if __name__ == "__main__":
    unittest.main()
