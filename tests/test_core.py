import importlib.util, unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'material_physics'/f'{name}.py')
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod
motion=load('water_motion'); types=load('material_types')
class CoreTests(unittest.TestCase):
    def test_density_equilibrium_and_fall(self):
        for density in (400.,600.,800.):
            frames,m=motion.simulate(density=density)
            self.assertAlmostEqual(m['final_submerged_fraction'],density/1000,delta=.015)
            self.assertLess(m['final_speed_m_s'],.06)
            self.assertGreater(m['first_contact_s'],.5)
            self.assertAlmostEqual(frames[6]['velocity'][2],-9.81*.25,places=6)
            for f in frames:
                self.assertTrue(np.isfinite(f['position']).all())
                self.assertAlmostEqual(np.linalg.norm(f['quaternion']),1.,places=8)
    def test_dense_solid_is_explicitly_unsupported(self):
        with self.assertRaises(ValueError): motion.simulate(density=1200)
    def test_uncertain_type_stays_manual(self):
        def result(name,share=80,votes=12):
            return {'candidates':[{'name':name,'share':share,'votes':votes}]}
        self.assertEqual(types.suggest_type(result('Wood')),'SOLID')
        self.assertEqual(types.suggest_type(result('Water')),'LIQUID')
        self.assertIsNone(types.suggest_type(result('Wood',59)))
        self.assertIsNone(types.suggest_type(result('Water',80,8)))
        self.assertIsNone(types.suggest_type(result('Paint/plaster/enamel')))
if __name__=='__main__': unittest.main()
