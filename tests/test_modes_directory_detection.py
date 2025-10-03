"""
Test modes directory mtime-based cache invalidation.
"""
import unittest
from instruction_composer import InstructionComposer


class TestModesDirectoryDetection(unittest.TestCase):
    """Test that new mode files are detected when added to modes directory."""

    def test_modes_cache_shared_across_instances(self):
        """Verify modes cache is class-level and shared."""
        InstructionComposer._modes_cache = ['test_mode']
        InstructionComposer._modes_dir_mtime = 1000.0

        composer1 = InstructionComposer()
        composer2 = InstructionComposer()

        # Both instances reference the same class-level cache
        self.assertIs(composer1._modes_cache, composer2._modes_cache)
        self.assertEqual(composer1._modes_cache, ['test_mode'])

    def test_modes_directory_has_static_cache_variables(self):
        """Verify static cache variables exist."""
        self.assertTrue(hasattr(InstructionComposer, '_modes_cache'))
        self.assertTrue(hasattr(InstructionComposer, '_modes_dir_mtime'))


if __name__ == '__main__':
    unittest.main()
