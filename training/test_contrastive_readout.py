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
    def test_residual_classes_preserve_initial_probabilities_and_frozen_encoder(self):
        import tensorflow as tf
        from contrastive_readout import attach,attach_frozen_residual,PHRASES
        inp=tf.keras.Input((8,));norm=tf.keras.layers.BatchNormalization()
        base=tf.keras.Model(inp,tf.keras.layers.Dense(1,activation='sigmoid')(norm(inp)))
        original,_=attach(base,warm_start=True)
        rng=np.random.default_rng(4);head=original.get_layer('near_phrase_probability')
        head.set_weights([rng.normal(0,.1,(8,len(PHRASES))).astype(np.float32),rng.normal(0,.1,len(PHRASES)).astype(np.float32)])
        x=rng.normal(size=(20,8)).astype(np.float32);before=original(x,training=False).numpy()
        fit,view=attach_frozen_residual(original,32)
        np.testing.assert_allclose(fit(x,training=False),before,atol=1e-6)
        np.testing.assert_allclose(view(x,training=False),before[:,1:2],atol=1e-6)
        frozen={layer.name:[v.copy() for v in layer.get_weights()] for layer in fit.layers if not layer.trainable}
        fit.compile(optimizer=tf.keras.optimizers.Adam(.01),loss='sparse_categorical_crossentropy')
        for _ in range(3):fit.train_on_batch(x,np.arange(20)%len(PHRASES))
        for layer in fit.layers:
            if layer.name in frozen:
                for a,b in zip(frozen[layer.name],layer.get_weights()):np.testing.assert_array_equal(a,b)
        np.testing.assert_array_equal(original(x,training=False),before)
        self.assertGreater(float(np.max(abs(fit(x,training=False).numpy()-before))),1e-5)
        np.testing.assert_allclose(view(x,training=False),fit(x,training=False)[:,1:2],atol=1e-6)

    def test_freezing_scalar_view_keeps_shared_training_normalization_fixed(self):
        import tensorflow as tf
        from contrastive_readout import attach
        from residual_readout import freeze_normalization
        inp=tf.keras.Input((8,))
        norm=tf.keras.layers.BatchNormalization()
        base=tf.keras.Model(inp,tf.keras.layers.Dense(1,activation='sigmoid')(norm(inp)))
        fit,view=attach(base,warm_start=True)
        freeze_normalization(view)
        before=[v.numpy().copy() for v in norm.weights]
        head=fit.get_layer('near_phrase_probability')
        head_before=[v.copy() for v in head.get_weights()]
        fit.compile(optimizer=tf.keras.optimizers.SGD(.1),loss='sparse_categorical_crossentropy')
        fit.train_on_batch(np.full((6,8),12.,np.float32),np.arange(6))
        for original,actual in zip(before,norm.get_weights()):np.testing.assert_array_equal(original,actual)
        self.assertTrue(any(not np.array_equal(a,b) for a,b in zip(head_before,head.get_weights())))

    def test_widened_trained_head_preserves_every_class_and_can_learn(self):
        import tempfile,json,hashlib
        from pathlib import Path
        import tensorflow as tf
        from contrastive_readout import attach,widen_readout
        def binary(architecture):
            inp=tf.keras.Input((8,));h=tf.keras.layers.Dense(architecture['filters'],activation='relu')(inp)
            return tf.keras.Model(inp,tf.keras.layers.Dense(1,activation='sigmoid')(h))
        source={'filters':4,'first_filters':3,'kernels':[3,5]};target={**source,'filters':7,'first_filters':5,'window_frames':198}
        tf.keras.utils.set_random_seed(109);fit,scalar=attach(binary(source),warm_start=True)
        fixture=np.random.default_rng(109).normal(size=(6,8)).astype('float32')
        fit.compile(optimizer=tf.keras.optimizers.SGD(.1),loss='sparse_categorical_crossentropy');fit.train_on_batch(fixture,np.arange(6))
        expected=fit(fixture).numpy()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'checkpoint.weights.h5';scalar.save_weights(path)
            (root/'report.json').write_text(json.dumps({**source,'feature_config':{'window_frames':198},
                'classifier_readout':{'type':'warm-plain-near-phrase','classes':PHRASES},'checkpoint_weights_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}))
            wide,view=attach(binary(target),warm_start=True);proof=widen_readout(wide,view,path,fixture,target,binary)
            np.testing.assert_allclose(wide(fixture).numpy(),expected,atol=1e-6)
            self.assertTrue(proof['new_channels_trainable'])
            wide.compile(optimizer=tf.keras.optimizers.SGD(.1),loss='sparse_categorical_crossentropy')
            wide.train_on_batch(fixture,np.arange(6));self.assertFalse(np.allclose(wide(fixture).numpy(),expected))
            with self.assertRaisesRegex(ValueError,'temporal context'):widen_readout(wide,view,path,fixture,{**target,'window_frames':399},binary)

    def test_audited_training_epoch_restores_all_class_probabilities(self):
        import tempfile,json
        from pathlib import Path
        import tensorflow as tf
        from contrastive_readout import attach,resume_readout
        from epoch_provenance import record
        tf.keras.utils.set_random_seed(91)
        x=np.random.default_rng(91).normal(size=(6,8)).astype('float32')
        inp=tf.keras.Input((8,));base=tf.keras.Model(inp,tf.keras.layers.Dense(1,activation='sigmoid')(inp))
        fit,view=attach(base,warm_start=True)
        fit.compile(optimizer=tf.keras.optimizers.Adam(.01),loss='sparse_categorical_crossentropy')
        fit.train_on_batch(x,np.arange(6));expected=fit(x).numpy()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'epochs').mkdir();checkpoint=root/'epochs/epoch-01.weights.h5';fit.save_weights(checkpoint)
            architecture={'filters':128,'first_filters':64,'kernels':[5,9]}
            (root/'report.json').write_text(json.dumps({**architecture,'epochs':1,'export_only':False,
                'classifier_readout':{'type':'warm-plain-near-phrase','classes':PHRASES},'checkpoint_weights_sha256':'different-best-checkpoint'}))
            (root/'training-history.json').write_text(json.dumps({'loss':[1.]}));record(root)
            fresh,scalar=attach(base,warm_start=True)
            proof=resume_readout(fresh,scalar,checkpoint,x,architecture)
            np.testing.assert_allclose(fresh(x).numpy(),expected,atol=1e-7)
            self.assertEqual(proof['source_epoch']['epoch'],1)

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
