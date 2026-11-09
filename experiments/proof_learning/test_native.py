"""Integration: DDS_PROOF_BINARY, DDS_PROOF_MODEL, DDS_PROOF_DATA select fixtures."""
import json
import ctypes as C
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import numpy as np
from pipeline import features, forward


@unittest.skipUnless(os.environ.get('DDS_PROOF_BINARY'), 'native fixture not supplied')
class NativeTest(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('DDS_PROOF_ROOTS'), 'root fixtures not supplied')
    def test_root_only_gate_skips_small_requests_and_never_enters_children(self):
        rows = Path(os.environ['DDS_PROOF_ROOTS']).read_text().splitlines()
        chosen = []
        for large in [False, True]:
            chosen.append(next(r for r in rows if ((int(r.split()[26]) + 7) // 4 >= 10) == large))
        with tempfile.TemporaryDirectory() as directory:
            source, result = Path(directory) / 'roots', Path(directory) / 'results'
            source.write_text('\n'.join(chosen) + '\n')
            subprocess.run([os.environ['DDS_PROOF_BINARY'], 'evaluate', str(source), str(result),
                            os.environ['DDS_PROOF_MODEL'], '1', '1', '10'], check=True)
            outputs = [json.loads(r) for r in result.read_text().splitlines()]
            self.assertEqual(outputs[0]['model_calls'], 0)
            for row in outputs:
                self.assertTrue(row['all_moves_equal'])
                self.assertLessEqual(row['model_calls'], 3)
                if row['model_calls']:
                    self.assertEqual(row['min_model_depth'], row['root_depth'])
                    self.assertEqual(row['max_model_depth'], row['root_depth'])

    @unittest.skipUnless(os.environ.get('DDS_PROOF_REFERENCE'), 'reference DDS not supplied')
    def test_cutoff_labels_match_independent_exact_all_move_scores(self):
        class Deal(C.Structure):
            _fields_ = [('trump', C.c_int), ('first', C.c_int),
                        ('suits', C.c_int * 3), ('ranks', C.c_int * 3),
                        ('hands', (C.c_uint * 4) * 4)]
        class Future(C.Structure):
            _fields_ = [('nodes', C.c_int), ('cards', C.c_int)] + [
                (name, C.c_int * 13) for name in ['suit', 'rank', 'equals', 'score']]
        lib = C.CDLL(os.environ['DDS_PROOF_REFERENCE'])
        lib.dds_c_create_solvercontext.argtypes = [C.c_int] * 3
        lib.dds_c_create_solvercontext.restype = C.c_void_p
        lib.dds_c_destroy_solvercontext.argtypes = [C.c_void_p]
        lib.dds_c_solve_board.argtypes = [C.c_void_p, C.POINTER(Deal), C.c_int, C.c_int, C.c_int, C.POINTER(Future)]
        ctx = lib.dds_c_create_solvercontext(2, 16, 64)
        self.assertTrue(ctx)
        rows = [json.loads(x) for x in Path(os.environ['DDS_PROOF_DATA']).read_text().splitlines()]
        checked = 0
        try:
            for row in rows[::max(1, len(rows) // 100)]:
                k = row['key']; d = Deal(trump=k[19], first=k[17])
                for h in range(4):
                    for s in range(4):
                        d.hands[h][s] = k[4 * h + s] << 2
                for i in range(k[18]):
                    d.suits[i], d.ranks[i] = divmod(k[21 + i], 16)
                result = Future()
                self.assertEqual(lib.dds_c_solve_board(ctx, C.byref(d), -1, 3, 1, C.byref(result)), 1)
                values = {}
                for i in range(result.cards):
                    for rank in range(2, 15):
                        if (result.equals[i] | (1 << result.rank[i])) & (1 << rank):
                            values[result.suit[i] * 13 + rank - 2] = result.score[i]
                actor = (k[17] + k[18]) % 4
                residual = k[16] if k[16] < 32768 else k[16] - 65536
                need = residual if ((actor % 2 == 0) == bool(k[20])) else (k[24] + 7) // 4 - residual + 1
                for card, success, _ in row['moves']:
                    self.assertEqual(success, int(values[card] >= need))
                    checked += 1
        finally:
            lib.dds_c_destroy_solvercontext(ctx)
        print(json.dumps(dict(independent_cutoff_labels_checked=checked)))

    def test_exported_network_matches_numpy_and_benchmarks_full_choice(self):
        rows = [json.loads(x) for x in Path(os.environ['DDS_PROOF_DATA']).read_text().splitlines()[:100]]
        model_path = Path(os.environ['DDS_PROOF_MODEL'])
        archive = np.load(model_path.with_suffix('.npz'))
        model = {'w': [archive[f'w{i}'] for i in range(4)]}
        with tempfile.TemporaryDirectory() as directory:
            source, result = Path(directory) / 'input', Path(directory) / 'result'
            with source.open('w') as f:
                for r in rows:
                    f.write(' '.join(map(str, [*r['key'], len(r['moves']), *[m[0] for m in r['moves']]])) + '\n')
            subprocess.run([os.environ['DDS_PROOF_BINARY'], 'infer', str(model_path), str(source), str(result)], check=True)
            outputs = [json.loads(x) for x in result.read_text().splitlines()]
            self.assertEqual(len(outputs), len(rows) + 1)
            expected, _ = forward(model, np.stack([features(r['key'], [m[0] for m in r['moves']]) for r in rows]))
            np.testing.assert_allclose(np.asarray(outputs[:-1]), expected, rtol=1e-4, atol=5e-5)
            self.assertGreater(outputs[-1]['microseconds_per_choice'], 0)
            print(json.dumps(outputs[-1]))


if __name__ == '__main__':
    unittest.main()
