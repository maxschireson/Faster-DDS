import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import numpy as np
from train_delta import encode, predict


@unittest.skipUnless(os.environ.get('DDS_DELTA_MODEL'), 'delta fixture not supplied')
class DeltaNativeTest(unittest.TestCase):
    def test_native_predictions_match_numpy_and_measure_choice_latency(self):
        rows = [json.loads(x) for x in Path(os.environ['DDS_DELTA_DATA']).read_text().splitlines()[:100]]
        model_path = Path(os.environ['DDS_DELTA_MODEL'])
        archive = np.load(model_path.with_suffix('.npz'))
        model = dict(w=[archive[f'w{i}'] for i in range(4)])
        with tempfile.TemporaryDirectory() as directory:
            src, dst = Path(directory)/'input', Path(directory)/'output'
            src.write_text(''.join(' '.join(map(str,[*r['key'],r['ply_from_root'],len(r['stock_order']),*r['stock_order']]))+'\n' for r in rows))
            subprocess.run([os.environ['DDS_PROOF_BINARY'],'delta-infer',str(model_path),str(src),str(dst)],check=True)
            outputs = [json.loads(x) for x in dst.read_text().splitlines()]
            np.testing.assert_allclose(outputs[:-1],predict(model,np.stack([encode(r) for r in rows])),rtol=1e-4,atol=2e-6)
            self.assertGreater(outputs[-1]['microseconds_per_choice'],0)
            print(json.dumps(outputs[-1]))

    def test_causal_hook_limits_deviations_and_preserves_full_root_scores(self):
        rows = Path(os.environ['DDS_PROOF_ROOTS']).read_text().splitlines()
        chosen = [next(r for r in rows if ((int(r.split()[26])+7)//4>=10)==large) for large in [False,True]]
        with tempfile.TemporaryDirectory() as directory:
            src,dst=Path(directory)/'input',Path(directory)/'output'
            src.write_text('\n'.join(chosen)+'\n')
            # A very low threshold abstains; a high one forces the first eligible deviation.
            for threshold in ['-100','100']:
                subprocess.run([os.environ['DDS_PROOF_BINARY'],'delta',str(src),str(dst),os.environ['DDS_DELTA_MODEL'],threshold],check=True)
                outputs=[json.loads(x) for x in dst.read_text().splitlines()]
                self.assertEqual(outputs[0]['model_calls'],0)
                self.assertTrue(all(r['all_moves_equal'] for r in outputs))
                self.assertLessEqual(outputs[1]['model_calls'],3*64)
                self.assertLessEqual(outputs[1]['deviations'],3)
                if threshold=='-100':
                    self.assertEqual(outputs[1]['deviations'],0)
                    self.assertEqual(outputs[1]['baseline_nodes'],outputs[1]['model_nodes'])
                else:self.assertEqual(outputs[1]['deviations'],3)


if __name__=='__main__':unittest.main()
