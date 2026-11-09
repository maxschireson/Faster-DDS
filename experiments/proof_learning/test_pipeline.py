import unittest
import numpy as np
from pipeline import features, split_families, prepare_roots, train_step, initialize


class PipelineTest(unittest.TestCase):
    def test_features_rotate_to_actor_and_condition_on_target(self):
        key = [0] * 26
        key[4] = 1 << 12  # East holds spade ace; actor East.
        key[16:21] = [7, 0, 1, 4, 1]
        key[21] = 2
        key[24] = 47
        x = features(key, [12])
        self.assertEqual(x.shape, (427,))
        self.assertEqual(x[12], 1)
        self.assertEqual(x[208], 1)
        self.assertAlmostEqual(x[373], 7 / 13)
        self.assertEqual(x[375 + 12], 1)

    def test_family_split_is_stable_and_disjoint(self):
        a = split_families([str(i) for i in range(20)])
        b = split_families([str(i) for i in reversed(range(20))])
        self.assertEqual(a, b)
        self.assertEqual(set(a.values()), {'train', 'validation', 'test'})

    def test_roots_deduplicate_across_families_before_splitting(self):
        q = dict(worlds=[[[0], [13], [26], [39]]], trump=4, leader=0, trick=[])
        boards = [dict(family='a', queries=[q]), dict(family='b', queries=[q])]
        self.assertEqual(len(prepare_roots(boards, 10, 7)), 1)

    def test_both_training_heads_learn(self):
        model = initialize(7)
        x = np.zeros((4, 427), np.float32)
        x[:, 0] = 1
        success = np.ones((4, 52), np.float32)
        cost = np.ones((4, 52), np.float32)
        mask = np.ones((4, 52), np.float32)
        first = train_step(model, x, success, cost, mask, learning_rate=0.01)
        for _ in range(50):
            last = train_step(model, x, success, cost, mask, learning_rate=0.01)
        self.assertLess(last, first * 0.5)


if __name__ == '__main__':
    unittest.main()
