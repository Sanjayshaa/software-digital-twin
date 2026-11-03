import unittest
import sys
import os

backend_dir = os.path.abspath("backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

loader = unittest.TestLoader()
suite = unittest.TestSuite()

suite.addTests(loader.discover("backend/tests", pattern="test_blast_radius_phase1_lifecycle.py"))
suite.addTests(loader.discover("backend/tests", pattern="test_blast_radius_provenance.py"))
suite.addTests(loader.discover("backend/tests", pattern="test_pr_impact_integration.py"))

runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)

sys.exit(0 if result.wasSuccessful() else 1)
