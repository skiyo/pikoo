import importlib.util
import unittest
import numpy as np
from contrastive_readout import category,expanded_labels,PHRASES


class LabelsTest(unittest.TestCase):
    def test_only_full_annotated_near_phrases_receive_contrast_classes(self):
        row={'label':0,'text':'你好皮球'}
        self.assertEqual(category(row),PHRASES.index('你好皮球'))
        self.assertEqual(category(row,True),0)
        self.assertEqual(category({**row,'mined_training_prefix':True}),0)
        self.assertEqual(category({'label':0,'text':'普通聊天'}),0)
        self.assertEqual(category({'label':1,'text':'你好Pikoo'}),1)
    def test_repetitions_prefixes_and_silence_match_binary_dataset(self):
        rows=[{'split':'train','label':0,'text':'你好皮球','hard_negative':True},
              {'split':'train','label':1,'text':'你好皮酷'},
              {'split':'train','label':0,'text':'你好朋友','real_child':True},
              {'split':'validation','label':0,'text':'你好皮'}]
        result=expanded_labels(rows,3,2,4,True)
        self.assertEqual(result['train'][:8].tolist(),[3,0,3,0,1,1,1,10])
        self.assertEqual(len(result['train']),108)
        self.assertEqual(result['validation'][0],2)
        with self.assertRaisesRegex(ValueError,'Protected'):
            expanded_labels([{'split':'train','label':1,'frozen_holdout':True}],1,1,1,False)


@unittest.skipUnless(importlib.util.find_spec('tensorflow'),'Optional TensorFlow unavailable')
class ModelTest(unittest.TestCase):
    def test_trained_class_resume_preserves_all_classes_and_rejects_reordered_labels(self):
        import tempfile,json,hashlib
        from pathlib import Path
        import tensorflow as tf
        from contrastive_readout import attach,resume_readout
        tf.keras.utils.set_random_seed(73)
        inp=tf.keras.Input((8,));binary=tf.keras.Model(inp,tf.keras.layers.Dense(1,activation='sigmoid')(inp))
        fit,view=attach(binary,warm_start=True);fixture=np.random.default_rng(73).normal(size=(6,8)).astype('float32')
        fit.compile(optimizer=tf.keras.optimizers.SGD(.1),loss='sparse_categorical_crossentropy')
        fit.train_on_batch(fixture,np.array([0,1,2,3,4,5],np.float32));expected=fit(fixture).numpy()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'checkpoint.weights.h5';view.save_weights(path)
            architecture={'filters':128,'first_filters':64,'kernels':[5,9]}
            report={**architecture,'classifier_readout':{'type':'warm-plain-near-phrase','classes':PHRASES},
                    'checkpoint_weights_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
            (root/'report.json').write_text(json.dumps(report))
            fresh,scalar=attach(binary,warm_start=True);proof=resume_readout(fresh,scalar,path,fixture,architecture)
            self.assertTrue(proof['class_order_verified'])
            np.testing.assert_allclose(fresh(fixture).numpy(),expected,atol=1e-7)
            report['classifier_readout']['classes']=list(reversed(PHRASES));(root/'report.json').write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError,'class mapping'):resume_readout(fresh,scalar,path,fixture,architecture)

    def test_warm_start_preserves_nonzero_sigmoid_and_initial_non_target_mass(self):
        import tensorflow as tf
        from contrastive_readout import attach
        tf.keras.utils.set_random_seed(37)
        inp=tf.keras.Input((8,));last=tf.keras.layers.Dense(1,activation='sigmoid')(inp)
        binary=tf.keras.Model(inp,last)
        fixture=np.random.default_rng(37).normal(size=(12,8)).astype('float32')
        expected=binary(fixture).numpy().ravel()
        with self.assertRaisesRegex(ValueError,'zero wake classifier'):attach(binary)
        train,infer=attach(binary,warm_start=True)
        np.testing.assert_allclose(infer(fixture).numpy().ravel(),expected,atol=2e-7)
        probabilities=train(fixture).numpy()
        np.testing.assert_allclose(probabilities.sum(axis=1),1.,atol=2e-7)
        for index in [0,2,len(PHRASES)-1]:
            np.testing.assert_allclose(probabilities[:,index],(1-expected)/(len(PHRASES)-1),atol=2e-7)

    def test_scalar_probability_preserved_and_shared_multiclass_weights_train(self):
        import tensorflow as tf
        from contrastive_readout import attach
        tf.keras.utils.set_random_seed(31)
        inp=tf.keras.Input((8,));last=tf.keras.layers.Dense(1,activation='sigmoid',kernel_initializer='zeros',bias_initializer='zeros')(inp)
        binary=tf.keras.Model(inp,last);train,infer=attach(binary)
        fixture=np.random.default_rng(31).normal(size=(6,8)).astype('float32')
        np.testing.assert_allclose(infer(fixture).numpy(),binary(fixture).numpy(),atol=1e-7)
        train.compile(optimizer=tf.keras.optimizers.SGD(.1),loss='sparse_categorical_crossentropy')
        train.train_on_batch(fixture,np.array([0,1,2,3,4,5],np.float32))
        np.testing.assert_allclose(infer(fixture).numpy().ravel(),train(fixture).numpy()[:,1])
        self.assertFalse(np.allclose(infer(fixture).numpy(),.5))


if __name__=='__main__':unittest.main()
