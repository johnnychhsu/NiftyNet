import numpy as np
import tensorflow as tf

from base import Layer
from bn import BNLayer
from activation import ActiLayer
import layer_util


SUPPORTED_PADDING = set(['SAME', 'VALID'])

def default_w_initializer(kernel_shape):
    stddev = np.sqrt(2.0 / np.prod(kernel_shape[:-1]))
    return tf.truncated_normal_initializer(
            mean=0.0, stddev=stddev, dtype=tf.float32)

def default_b_initializer():
    return tf.zeros_initializer()


class ConvLayer(Layer):
    """
    This class defines a simple convolution with an optional bias term.
    Please consider `ConvolutionalLayer` if batch_norm and activation
    are also used.
    """
    def __init__(self,
                 n_output_chns,
                 kernel_size=3,
                 stride=1,
                 padding='SAME',
                 w_initializer=None,
                 w_regularizer=None,
                 with_bias=False,
                 b_initializer=None,
                 b_regularizer=None,
                 name='conv'):
        self.padding = padding.upper()
        assert(self.padding in SUPPORTED_PADDING)

        self.layer_name = '{}'.format(name)
        super(ConvLayer, self).__init__(name=self.layer_name)

        self.n_output_chns = n_output_chns
        self.kernel_size = np.asarray(kernel_size).flatten()
        self.stride = np.asarray(stride).flatten()
        self.with_bias = with_bias

        self.w_initializer = w_initializer
        self.w_regularizer = w_regularizer
        self.b_initializer = b_initializer
        self.b_regularizer = b_regularizer

        self._w = None
        self._b = None

    def layer_op(self, input_tensor):
        input_shape = input_tensor.get_shape().as_list()
        n_input_chns = input_shape[-1]
        spatial_rank = layer_util.infer_spatial_rank(input_tensor)

        # initialize conv kernels/strides and then apply
        w_full_size = np.vstack((
            [self.kernel_size] * spatial_rank,
            n_input_chns, self.n_output_chns)).flatten()
        full_stride = np.vstack((
            [self.stride] * spatial_rank)).flatten()
        if self.w_initializer is None:
            self.w_initializer = default_w_initializer(w_full_size)
        self._w = tf.get_variable(
                'w', shape=w_full_size.tolist(),
                initializer=self.w_initializer,
                regularizer=self.w_regularizer)
        output_tensor = tf.nn.convolution(input=input_tensor,
                                          filter=self._w,
                                          strides=full_stride.tolist(),
                                          padding=self.padding,
                                          name='conv')
        if not self.with_bias:
            return output_tensor

        # adding the bias term
        if self.b_initializer is None:
            self.b_initializer = default_b_initializer()
        self._b = tf.get_variable(
                'b', shape=(self.n_output_chns),
                initializer=self.b_initializer,
                regularizer=self.b_regularizer)
        output_tensor = tf.nn.bias_add(output_tensor, self._b, name='add_bias')
        return output_tensor


class ConvolutionalLayer(Layer):
    """
    This class defines a composite layer with optional components:
        convolution -> batch_norm -> activation -> dropout
    """
    def __init__(self,
                 n_output_chns,
                 kernel_size,
                 stride=1,
                 padding='SAME',
                 w_initializer=None,
                 w_regularizer=None,
                 with_bias=False,
                 b_initializer=None,
                 b_regularizer=None,
                 with_bn=True,
                 bn_regularizer=None,
                 acti_fun=None,
                 name="conv"):

        self.with_bias = with_bias
        self.acti_fun = acti_fun
        self.with_bn = with_bn
        self.layer_name = '{}'.format(name)
        if self.with_bn:
            self.layer_name += '_bn'
        if (self.acti_fun is not None):
            self.layer_name += '_{}'.format(self.acti_fun)
        super(ConvolutionalLayer, self).__init__(name=self.layer_name)

        self.n_output_chns = n_output_chns
        self.kernel_size = kernel_size
        self.stride = stride
        self.padding = padding

        self.w_initializer = w_initializer
        self.w_regularizer = w_regularizer
        self.b_initializer = b_initializer
        self.b_regularizer = b_regularizer
        self.bn_regularizer = bn_regularizer

        self.conv_layer = None
        self.bn_layer = None
        self.acti_layer = None
        self.dropout_layer = None

    def layer_op(self, input_tensor, is_training, keep_prob=None):
        # init sub-layers
        self.conv_layer = ConvLayer(n_output_chns=self.n_output_chns,
                                    kernel_size=self.kernel_size,
                                    stride=self.stride,
                                    padding=self.padding,
                                    w_initializer=self.w_initializer,
                                    w_regularizer=self.w_regularizer,
                                    with_bias=self.with_bias,
                                    b_initializer=self.b_initializer,
                                    b_regularizer=self.b_regularizer,
                                    name='conv_')
        output_tensor = self.conv_layer(input_tensor)

        if self.with_bn:
            self.bn_layer = BNLayer(regularizer=self.bn_regularizer, name='bn_')
            output_tensor = self.bn_layer(output_tensor, is_training)

        if (self.acti_fun is not None):
            self.acti_layer = ActiLayer(func=self.acti_fun,
                                        regularizer=self.w_regularizer,
                                        name='acti_')
            output_tensor = self.acti_layer(output_tensor)

        if (keep_prob is not None):
            self.dropout_layer = ActiLayer(func='dropout', name='dropout_')
            output_tensor = self.dropout_layer(output_tensor,
                                               keep_prob=keep_prob)
        return output_tensor
