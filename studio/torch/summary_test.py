import unittest
from io import StringIO

from studio.torch import summary


class ReporterTest(unittest.TestCase):

    def test_summary_report(self):
        r = summary.Reporter(log_interval=2, smooth_interval=2)
        out = StringIO()
        r.add(0, 'k', 0.1)
        r.add(1, 'k', 0.2)
        r.report()
        r.add(2, 'k', 0.3)
        r.report(out)
        self.assertEqual(out.getvalue(), "Step 2: k = 0.25000")


if __name__ == "__main__":
    unittest.main()
