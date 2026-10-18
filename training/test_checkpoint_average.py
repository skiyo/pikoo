import unittest
import numpy as np
from checkpoint_average import interpolate


class CheckpointAverageTest(unittest.TestCase):
    def test_interpolation_preserves_identical_weights_and_does_not_mutate_sources(self):
        a=[np.array([[1.,2.]],np.float32),np.array([4.],np.float32)]
        b=[np.array([[5.,10.]],np.float32),np.array([8.],np.float32)]
        c=interpolate(a,b,.25)
        np.testing.assert_array_equal(c[0],[[2.,4.]])
        np.testing.assert_array_equal(c[1],[5.])
        for x,y in zip(a,interpolate(a,a,.5)):np.testing.assert_array_equal(x,y)
        c[0][0,0]=100
        self.assertEqual(a[0][0,0],1.)
        for fraction in [0,1,float('nan')]:
            with self.assertRaises(ValueError):interpolate(a,b,fraction)
        for malformed in [[],[np.ones(3,np.float32)],[np.ones((1,2),np.int32),b[1]],
                [np.array([[float('nan'),1]],np.float32),b[1]]]:
            with self.assertRaises(ValueError):interpolate(a,malformed,.5)


if __name__=='__main__':unittest.main()
