import unittest
import numpy as np
from train_delta import encode, initialize, step, predict, partition, baseline_loss, loss_parts, checked_partition


class DeltaTest(unittest.TestCase):
    def test_fixed_family_assignment_survives_subsampling_and_enforces_training_minimum(self):
        rows=[dict(family=f,root=i,decision_index=1,key=[i],stock_order=[1,2]) for i,f in enumerate('abcd')]
        splits=dict(a='test',b='train',c='validation',d='train')
        groups,_=checked_partition(rows,splits,2)
        self.assertEqual({r['family'] for r in groups['train']},{'b','d'})
        with self.assertRaises(ValueError):checked_partition(rows,splits,1000)
        reduced,_=checked_partition(rows[:3],splits,1)
        self.assertEqual(reduced['test'][0]['family'],'a')

    def test_partition_removes_duplicate_observations_and_cross_split_states(self):
        rows = [dict(family=f, root=i, decision_index=1, key=[i], stock_order=[1, 2]) for i,f in enumerate('abcdefghij')]
        from pipeline import split_families
        splits = split_families(r['family'] for r in rows)
        train = next(r for r in rows if splits[r['family']] == 'train')
        test = next(r for r in rows if splits[r['family']] == 'test')
        test['key'] = train['key']
        groups, report = partition(rows + [train.copy()], splits)
        self.assertEqual(report['duplicate_observations'], 1)
        self.assertEqual(report['cross_split_rows'], 2)
        self.assertEqual(sum(map(len, groups.values())), 8)

    def test_baseline_uses_same_weighted_censored_huber_loss(self):
        model = initialize(1)
        for w in model['w']: w.fill(0)
        data = (np.zeros((2,480),np.float32), np.full((2,3),2,np.float32),
                np.ones((2,3)), np.ones((2,3)), np.array([[1],[5]]))
        self.assertAlmostEqual(baseline_loss(*data), loss_parts(model,*data)[0])

    def test_inputs_include_stock_order_but_not_measured_future_cost(self):
        key = [0] * 26; key[19] = 4; key[24] = 48
        row = dict(key=key, stock_order=[12, 8, 0], ply_from_root=2, baseline_nodes=100)
        a = encode(row)
        row['baseline_nodes'] = 999999
        np.testing.assert_array_equal(a, encode(row))
        self.assertEqual(a.shape, (480,))
        self.assertEqual(a[427 + 12], 1)
        self.assertEqual(a[427 + 8], 0.5)
        self.assertEqual(a[427], np.float32(1 / 3))

    def test_cost_lower_bound_does_not_penalize_higher_prediction(self):
        model = initialize(1)
        for w in model['w']: w.fill(0)
        model['w'][-1].fill(2)
        x = np.zeros((1, 480), np.float32)
        y = np.ones((1, 3), np.float32)
        before = [w.copy() for w in model['w']]
        step(model, x, y, np.ones_like(y), np.zeros_like(y), np.ones((1, 1)))
        for a, b in zip(before, model['w']):np.testing.assert_array_equal(a, b)

    def test_network_learns_deviation_cost(self):
        model = initialize(1)
        x = np.ones((8, 480), np.float32)
        y = np.full((8, 3), -0.2, np.float32)
        first = np.mean((predict(model, x) - y) ** 2)
        for _ in range(100):step(model, x, y, np.ones_like(y), np.ones_like(y), np.ones((8, 1)))
        self.assertLess(np.mean((predict(model, x) - y) ** 2), first / 10)


if __name__ == '__main__': unittest.main()
