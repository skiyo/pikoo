import unittest
from corpus_ancestry import parents


class CorpusAncestryTest(unittest.TestCase):
    def test_all_origins_are_retained_without_duplicate_edges(self):
        self.assertEqual(parents({'parent_sha256': 'a', 'augmentation': {'parent_sha256': 'b'},
                                  'ancestry_parents': ['a', 'c']}), {'a', 'b', 'c'})
        self.assertEqual(parents({}), set())

    def test_malformed_alternate_origins_cannot_silently_change_protection(self):
        for value in ('parent', None, [None], ['']):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parents({'ancestry_parents': value})


if __name__ == '__main__':
    unittest.main()
