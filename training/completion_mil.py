"""TRAIN-only positive event loss matching the existing five-step detector.

Negatives retain their full per-step categorical loss. A positive may satisfy
its target supervision in one complete five-step window within its existing
uncertain ending/completion region. Padding and early incomplete prefixes are
never eligible. This changes no inference graph, threshold or audio labels.
"""
import tensorflow as tf


def loss(labels, probabilities, weights, negative_events=False):
    labels = tf.cast(labels, tf.int32)
    probabilities = tf.convert_to_tensor(probabilities)
    weights = tf.cast(weights, probabilities.dtype)
    tf.debugging.assert_rank(probabilities, 3)
    tf.debugging.assert_equal(tf.shape(probabilities)[:2], tf.shape(labels))
    tf.debugging.assert_equal(tf.shape(weights), tf.shape(labels))
    tf.debugging.assert_non_negative(weights)
    tf.debugging.assert_all_finite(weights, 'Invalid sample weights')
    steps = tf.shape(labels)[1]
    tf.debugging.assert_greater_equal(steps, 5)
    positive = tf.reduce_any(labels == 1, axis=1)
    # The unchanged data contract always supervises the completion tail, so
    # its last nonzero weight gives the exact valid extent despite the ignored
    # interior interval. A zero right-padding prediction cannot win the loss.
    indices = tf.range(steps)[None, :]
    last_valid = tf.reduce_max(tf.where(weights > 0, indices, -1), axis=1)
    valid = indices <= last_valid[:, None]
    eligible = valid & positive[:, None] & ((weights == 0) | (labels == 1))
    windows = tf.nn.avg_pool1d(tf.cast(eligible, probabilities.dtype)[..., None], 5, 1, 'VALID')[..., 0]
    windows = windows >= 1-1e-6
    tf.debugging.assert_positive(tf.boolean_mask(tf.reduce_sum(tf.cast(windows, tf.int32), axis=1), positive),
                                 message='No eligible complete five-step positive window')
    wake = tf.nn.avg_pool1d(probabilities[..., 1:2], 5, 1, 'VALID')[..., 0]
    best = tf.reduce_max(tf.where(windows, wake, tf.zeros_like(wake)), axis=1)
    target_mass = tf.reduce_sum(tf.where(labels == 1, weights, tf.zeros_like(weights)), axis=1)/tf.cast(steps, weights.dtype)
    per_step = tf.keras.losses.sparse_categorical_crossentropy(labels, probabilities)
    other_loss = tf.reduce_sum(per_step*tf.where(labels == 1, tf.zeros_like(weights), weights), axis=1)/tf.cast(steps, weights.dtype)
    event_loss = -tf.math.log(tf.clip_by_value(best, 1e-7, 1.))*target_mass
    if negative_events:
        # A brief false event can be diluted by hundreds of correct frames.
        # Sum non-wake classes directly instead of subtracting a rounded1.0
        # wake probability: this keeps gradients alive for saturated errors.
        nonwake = tf.reduce_sum(tf.concat([probabilities[..., :1], probabilities[..., 2:]], axis=-1),
                                axis=-1, keepdims=True)
        nonwake_windows = tf.nn.avg_pool1d(nonwake, 5, 1, 'VALID')[..., 0]
        valid_windows = indices[:, 4:] <= last_valid[:, None]
        worst_nonwake = tf.reduce_min(tf.where(valid_windows, nonwake_windows, tf.ones_like(nonwake_windows)), axis=1)
        penalty = -tf.math.log(tf.clip_by_value(worst_nonwake, 1e-30, 1.))
        event_loss += tf.where(positive, tf.zeros_like(penalty), penalty)
    return tf.reduce_mean(other_loss+event_loss)


def trainer(network, negative_events=False):
    """Train the existing network; save/export that network, not this wrapper."""
    class CompletionTrainer(tf.keras.Model):
        def __init__(self):
            super().__init__()
            self.network = network
            self.loss_tracker = tf.keras.metrics.Mean(name='loss')

        @property
        def metrics(self):
            return [self.loss_tracker]

        def call(self, inputs, training=False):
            return self.network(inputs, training=training)

        def train_step(self, data):
            x, labels, weights = tf.keras.utils.unpack_x_y_sample_weight(data)
            if weights is None:
                raise ValueError('Explicit causal masks/class weights are required')
            with tf.GradientTape() as tape:
                probabilities = self.network(x, training=True)
                total = loss(labels, probabilities, weights, negative_events=negative_events)
                if self.network.losses:
                    total += tf.add_n(self.network.losses)
            variables = self.network.trainable_variables
            gradients = tape.gradient(total, variables)
            self.optimizer.apply_gradients(zip(gradients, variables))
            self.loss_tracker.update_state(total, sample_weight=tf.cast(tf.shape(x)[0], tf.float32))
            return {'loss': self.loss_tracker.result()}

    return CompletionTrainer()
