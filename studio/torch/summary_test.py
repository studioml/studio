import sys

import unittest
from contextlib import contextmanager
from StringIO import StringIO

import summary


@contextmanager
def capture_output():
    new_out = StringIO()
    old_out = sys.stdout
    try:
        sys.stdout = new_out
        yield sys.stdout
    finally:
        sys.stdout = old_out


class ReporterTest(unittest.TestCase):

    def test_summary_report(self):
        r = summary.Reporter(log_interval=2, smooth_interval=2)
        with capture_output() as out:
            r.add(0, 'k', 0.1)
            r.add(1, 'k', 0.2)
            r.report()
            r.add(2, 'k', 0.3)
            r.report()
        self.assertEqual(out.getvalue(), "Step 2: k = 0.25000\n")


if __name__ == "__main__":
    unittest.main()
