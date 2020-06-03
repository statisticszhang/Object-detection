import os, math

import caffe
from caffe import layers as L
from caffe import params as P
from caffe.proto import caffe_pb2

def check_if_exist(path):
    return os.path.exists(path)

def make_if_not_exist(path):
    if not os.path.exists(path):
        os.makedirs(path)

def UnpackVariable(var, num):
  assert len > 0
  if type(var) is list and len(var) == num:
    return var
  else:
    ret = []
    if type(var) is list:
      assert len(var) == 1
      for i in xrange(0, num):
        ret.append(var[0])
    else:
      for i in xrange(0, num):
        ret.append(var)
    return ret

def ConvBNLayer(net, from_layer, out_layer, use_bn, use_relu, num_output,
    kernel_size, pad, stride, dilation=1, use_scale=True, lr_mult=1,
    conv_prefix='', conv_postfix='', bn_prefix='', bn_postfix='_bn',
    scale_prefix='', scale_postfix='_scale', bias_prefix='', bias_postfix='_bias',
    **bn_params):
  if use_bn:
    # parameters for convolution layer with batchnorm.
    kwargs = {
        'param': [dict(lr_mult=lr_mult, decay_mult=1)],
        'weight_filler': dict(type='gaussian', std=0.01),
        'bias_term': False,
        }
    eps = bn_params.get('eps', 0.001)
    moving_average_fraction = bn_params.get('moving_average_fraction', 0.999)
    use_global_stats = bn_params.get('use_global_stats', False)
    # parameters for batchnorm layer.
    bn_kwargs = {
        'param': [
            dict(lr_mult=0, decay_mult=0),
            dict(lr_mult=0, decay_mult=0),
            dict(lr_mult=0, decay_mult=0)],
        'eps': eps,
        'moving_average_fraction': moving_average_fraction,
        }
    bn_lr_mult = lr_mult
    if use_global_stats:
      # only specify if use_global_stats is explicitly provided;
      # otherwise, use_global_stats_ = this->phase_ == TEST;
      bn_kwargs = {
          'param': [
              dict(lr_mult=0, decay_mult=0),
              dict(lr_mult=0, decay_mult=0),
              dict(lr_mult=0, decay_mult=0)],
          'eps': eps,
          'use_global_stats': use_global_stats,
          }
      # not updating scale/bias parameters
      bn_lr_mult = 0
    # parameters for scale bias layer after batchnorm.
    if use_scale:
      sb_kwargs = {
          'bias_term': True,
          'param': [
              dict(lr_mult=bn_lr_mult, decay_mult=0),
              dict(lr_mult=bn_lr_mult, decay_mult=0)],
          'filler': dict(type='constant', value=1.0),
          'bias_filler': dict(type='constant', value=0.0),
          }
    else:
      bias_kwargs = {
          'param': [dict(lr_mult=bn_lr_mult, decay_mult=0)],
          'filler': dict(type='constant', value=0.0),
          }
  else:
    kwargs = {
        'param': [
            dict(lr_mult=lr_mult, decay_mult=1),
            dict(lr_mult=2 * lr_mult, decay_mult=0)],
        'weight_filler': dict(type='xavier'),
        'bias_filler': dict(type='constant', value=0)
        }

  conv_name = '{}{}{}'.format(conv_prefix, out_layer, conv_postfix)
  [kernel_h, kernel_w] = UnpackVariable(kernel_size, 2)
  [pad_h, pad_w] = UnpackVariable(pad, 2)
  [stride_h, stride_w] = UnpackVariable(stride, 2)
  if kernel_h == kernel_w:
    net[conv_name] = L.Convolution(net[from_layer], num_output=num_output,
        kernel_size=kernel_h, pad=pad_h, stride=stride_h, **kwargs)
  else:
    net[conv_name] = L.Convolution(net[from_layer], num_output=num_output,
        kernel_h=kernel_h, kernel_w=kernel_w, pad_h=pad_h, pad_w=pad_w,
        stride_h=stride_h, stride_w=stride_w, **kwargs)
  if dilation > 1:
    net.update(conv_name, {'dilation': dilation})
  if use_bn:
    bn_name = '{}{}{}'.format(bn_prefix, out_layer, bn_postfix)
    net[bn_name] = L.BatchNorm(net[conv_name], in_place=True, **bn_kwargs)
    if use_scale:
      sb_name = '{}{}{}'.format(scale_prefix, out_layer, scale_postfix)
      net[sb_name] = L.Scale(net[bn_name], in_place=True, **sb_kwargs)
    else:
      bias_name = '{}{}{}'.format(bias_prefix, out_layer, bias_postfix)
      net[bias_name] = L.Bias(net[bn_name], in_place=True, **bias_kwargs)
  if use_relu:
    relu_name = '{}_relu'.format(conv_name)
    net[relu_name] = L.ReLU(net[conv_name], in_place=True)

def ResBody(net, from_layer, block_name, out2a, out2b, out2c, stride, use_branch1, dilation=1, **bn_param):
  # ResBody(net, 'pool1', '2a', 64, 64, 256, 1, True)

  conv_prefix = 'res{}_'.format(block_name)
  conv_postfix = ''
  bn_prefix = 'bn{}_'.format(block_name)
  bn_postfix = ''
  scale_prefix = 'scale{}_'.format(block_name)
  scale_postfix = ''
  use_scale = True

  if use_branch1:
    branch_name = 'branch1'
    ConvBNLayer(net, from_layer, branch_name, use_bn=True, use_relu=False,
        num_output=out2c, kernel_size=1, pad=0, stride=stride, use_scale=use_scale,
        conv_prefix=conv_prefix, conv_postfix=conv_postfix,
        bn_prefix=bn_prefix, bn_postfix=bn_postfix,
        scale_prefix=scale_prefix, scale_postfix=scale_postfix, **bn_param)
    branch1 = '{}{}'.format(conv_prefix, branch_name)
  else:
    branch1 = from_layer

  branch_name = 'branch2a'
  ConvBNLayer(net, from_layer, branch_name, use_bn=True, use_relu=True,
      num_output=out2a, kernel_size=1, pad=0, stride=stride, use_scale=use_scale,
      conv_prefix=conv_prefix, conv_postfix=conv_postfix,
      bn_prefix=bn_prefix, bn_postfix=bn_postfix,
      scale_prefix=scale_prefix, scale_postfix=scale_postfix, **bn_param)
  out_name = '{}{}'.format(conv_prefix, branch_name)

  branch_name = 'branch2b'
  if dilation == 1:
    ConvBNLayer(net, out_name, branch_name, use_bn=True, use_relu=True,
        num_output=out2b, kernel_size=3, pad=1, stride=1, use_scale=use_scale,
        conv_prefix=conv_prefix, conv_postfix=conv_postfix,
        bn_prefix=bn_prefix, bn_postfix=bn_postfix,
        scale_prefix=scale_prefix, scale_postfix=scale_postfix, **bn_param)
  else:
    pad = int((3 + (dilation - 1) * 2) - 1) / 2
    ConvBNLayer(net, out_name, branch_name, use_bn=True, use_relu=True,
        num_output=out2b, kernel_size=3, pad=pad, stride=1, use_scale=use_scale,
        dilation=dilation, conv_prefix=conv_prefix, conv_postfix=conv_postfix,
        bn_prefix=bn_prefix, bn_postfix=bn_postfix,
        scale_prefix=scale_prefix, scale_postfix=scale_postfix, **bn_param)
  out_name = '{}{}'.format(conv_prefix, branch_name)

  branch_name = 'branch2c'
  ConvBNLayer(net, out_name, branch_name, use_bn=True, use_relu=False,
      num_output=out2c, kernel_size=1, pad=0, stride=1, use_scale=use_scale,
      conv_prefix=conv_prefix, conv_postfix=conv_postfix,
      bn_prefix=bn_prefix, bn_postfix=bn_postfix,
      scale_prefix=scale_prefix, scale_postfix=scale_postfix, **bn_param)
  branch2 = '{}{}'.format(conv_prefix, branch_name)

  res_name = 'res{}'.format(block_name)
  net[res_name] = L.Eltwise(net[branch1], net[branch2])
  relu_name = '{}_relu'.format(res_name)
  net[relu_name] = L.ReLU(net[res_name], in_place=True)

def InceptionTower(net, from_layer, tower_name, layer_params, **bn_param):
  use_scale = False
  for param in layer_params:
    tower_layer = '{}/{}'.format(tower_name, param['name'])
    del param['name']
    if 'pool' in tower_layer:
      net[tower_layer] = L.Pooling(net[from_layer], **param)
    else:
      param.update(bn_param)
      ConvBNLayer(net, from_layer, tower_layer, use_bn=True, use_relu=True,
          use_scale=use_scale, **param)
    from_layer = tower_layer
  return net[from_layer]

def CreateAnnotatedDataLayer(source, batch_size=32, backend=P.Data.LMDB,
        output_label=True, train=True, label_map_file='', anno_type=None,
        transform_param={}, batch_sampler=[{}]):
    if train:
        kwargs = {
                'include': dict(phase=caffe_pb2.Phase.Value('TRAIN')),
                'transform_param': transform_param,
                }
    else:
        kwargs = {
                'include': dict(phase=caffe_pb2.Phase.Value('TEST')),
                'transform_param': transform_param,
                }
    ntop = 1
    if output_label:
        ntop = 2
    annotated_data_param = {
        'label_map_file': label_map_file,
        'batch_sampler': batch_sampler,
        }
    if anno_type is not None:
        annotated_data_param.update({'anno_type': anno_type})
    return L.AnnotatedData(name="data", annotated_data_param=annotated_data_param,
        data_param=dict(batch_size=batch_size, backend=backend, source=source),
        ntop=ntop, **kwargs)

def VGGNetBody(net, from_layer, need_fc=True, fully_conv=False, reduced=False,
        dilated=False, nopool=False, dropout=True, freeze_layers=[], dilate_pool4=False):
    kwargs = {
            'param': [dict(lr_mult=1, decay_mult=1), dict(lr_mult=2, decay_mult=0)],
            'weight_filler': dict(type='xavier'),
            'bias_filler': dict(type='constant', value=0)}

    assert from_layer in net.keys()
    net.conv1_1 = L.Convolution(net[from_layer], num_output=64, pad=1, kernel_size=3, **kwargs)

    net.relu1_1 = L.ReLU(net.conv1_1, in_place=True)
    net.conv1_2 = L.Convolution(net.relu1_1, num_output=64, pad=1, kernel_size=3, **kwargs)
    net.relu1_2 = L.ReLU(net.conv1_2, in_place=True)

    if nopool:
        name = 'conv1_3'
        net[name] = L.Convolution(net.relu1_2, num_output=64, pad=1, kernel_size=3, stride=2, **kwargs)
    else:
        name = 'pool1'
        net.pool1 = L.Pooling(net.relu1_2, pool=P.Pooling.MAX, kernel_size=2, stride=2)

    net.conv2_1 = L.Convolution(net[name], num_output=128, pad=1, kernel_size=3, **kwargs)
    net.relu2_1 = L.ReLU(net.conv2_1, in_place=True)
    net.conv2_2 = L.Convolution(net.relu2_1, num_output=128, pad=1, kernel_size=3, **kwargs)
    net.relu2_2 = L.ReLU(net.conv2_2, in_place=True)

    if nopool:
        name = 'conv2_3'
        net[name] = L.Convolution(net.relu2_2, num_output=128, pad=1, kernel_size=3, stride=2, **kwargs)
    else:
        name = 'pool2'
        net[name] = L.Pooling(net.relu2_2, pool=P.Pooling.MAX, kernel_size=2, stride=2)

    net.conv3_1 = L.Convolution(net[name], num_output=256, pad=1, kernel_size=3, **kwargs)
    net.relu3_1 = L.ReLU(net.conv3_1, in_place=True)
    net.conv3_2 = L.Convolution(net.relu3_1, num_output=256, pad=1, kernel_size=3, **kwargs)
    net.relu3_2 = L.ReLU(net.conv3_2, in_place=True)
    net.conv3_3 = L.Convolution(net.relu3_2, num_output=256, pad=1, kernel_size=3, **kwargs)
    net.relu3_3 = L.ReLU(net.conv3_3, in_place=True)

    if nopool:
        name = 'conv3_4'
        net[name] = L.Convolution(net.relu3_3, num_output=256, pad=1, kernel_size=3, stride=2, **kwargs)
    else:
        name = 'pool3'
        net[name] = L.Pooling(net.relu3_3, pool=P.Pooling.MAX, kernel_size=2, stride=2)

    net.conv4_1 = L.Convolution(net[name], num_output=512, pad=1, kernel_size=3, **kwargs)
    net.relu4_1 = L.ReLU(net.conv4_1, in_place=True)
    net.conv4_2 = L.Convolution(net.relu4_1, num_output=512, pad=1, kernel_size=3, **kwargs)
    net.relu4_2 = L.ReLU(net.conv4_2, in_place=True)
    net.conv4_3 = L.Convolution(net.relu4_2, num_output=512, pad=1, kernel_size=3, **kwargs)
    net.relu4_3 = L.ReLU(net.conv4_3, in_place=True)

    if nopool:
        name = 'conv4_4'
        net[name] = L.Convolution(net.relu4_3, num_output=512, pad=1, kernel_size=3, stride=2, **kwargs)
    else:
        name = 'pool4'
        if dilate_pool4:
            net[name] = L.Pooling(net.relu4_3, pool=P.Pooling.MAX, kernel_size=3, stride=1, pad=1)
            dilation = 2
        else:
            net[name] = L.Pooling(net.relu4_3, pool=P.Pooling.MAX, kernel_size=2, stride=2)
            dilation = 1

    kernel_size = 3
    pad = int((kernel_size + (dilation - 1) * (kernel_size - 1)) - 1) / 2
    net.conv5_1 = L.Convolution(net[name], num_output=512, pad=pad, kernel_size=kernel_size, dilation=dilation, **kwargs)
    net.relu5_1 = L.ReLU(net.conv5_1, in_place=True)
    net.conv5_2 = L.Convolution(net.relu5_1, num_output=512, pad=pad, kernel_size=kernel_size, dilation=dilation, **kwargs)
    net.relu5_2 = L.ReLU(net.conv5_2, in_place=True)
    net.conv5_3 = L.Convolution(net.relu5_2, num_output=512, pad=pad, kernel_size=kernel_size, dilation=dilation, **kwargs)
    net.relu5_3 = L.ReLU(net.conv5_3, in_place=True)

    if need_fc:
        if dilated:
            if nopool:
                name = 'conv5_4'
                net[name] = L.Convolution(net.relu5_3, num_output=512, pad=1, kernel_size=3, stride=1, **kwargs)
            else:
                name = 'pool5'
                net[name] = L.Pooling(net.relu5_3, pool=P.Pooling.MAX, pad=1, kernel_size=3, stride=1)
        else:
            if nopool:
                name = 'conv5_4'
                net[name] = L.Convolution(net.relu5_3, num_output=512, pad=1, kernel_size=3, stride=2, **kwargs)
            else:
                name = 'pool5'
                net[name] = L.Pooling(net.relu5_3, pool=P.Pooling.MAX, kernel_size=2, stride=2)

        if fully_conv:
            if dilated:
                if reduced:
                    dilation = dilation * 6
                    kernel_size = 3
                    num_output = 1024
                else:
                    dilation = dilation * 2
                    kernel_size = 7
                    num_output = 4096
            else:
                if reduced:
                    dilation = dilation * 3
                    kernel_size = 3
                    num_output = 1024
                else:
                    kernel_size = 7
                    num_output = 4096
            pad = int((kernel_size + (dilation - 1) * (kernel_size - 1)) - 1) / 2
            net.fc6 = L.Convolution(net[name], num_output=num_output, pad=pad, kernel_size=kernel_size, dilation=dilation, **kwargs)

            net.relu6 = L.ReLU(net.fc6, in_place=True)
            if dropout:
                net.drop6 = L.Dropout(net.relu6, dropout_ratio=0.5, in_place=True)

            if reduced:
                net.fc7 = L.Convolution(net.relu6, num_output=1024, kernel_size=1, **kwargs)
            else:
                net.fc7 = L.Convolution(net.relu6, num_output=4096, kernel_size=1, **kwargs)
            net.relu7 = L.ReLU(net.fc7, in_place=True)
            if dropout:
                net.drop7 = L.Dropout(net.relu7, dropout_ratio=0.5, in_place=True)
        else:
            net.fc6 = L.InnerProduct(net.pool5, num_output=4096)
            net.relu6 = L.ReLU(net.fc6, in_place=True)
            if dropout:
                net.drop6 = L.Dropout(net.relu6, dropout_ratio=0.5, in_place=True)
            net.fc7 = L.InnerProduct(net.relu6, num_output=4096)
            net.relu7 = L.ReLU(net.fc7, in_place=True)
            if dropout:
                net.drop7 = L.Dropout(net.relu7, dropout_ratio=0.5, in_place=True)

    # Update freeze layers.
    kwargs['param'] = [dict(lr_mult=0, decay_mult=0), dict(lr_mult=0, decay_mult=0)]
    layers = net.keys()
    for freeze_layer in freeze_layers:
        if freeze_layer in layers:
            net.update(freeze_layer, kwargs)

    return net

def DSOD300_V3_Body(net, from_layer):

    def bn_relu_conv(bottom, ks, nout, stride, pad, dropout, inplace=True):
        batch_norm = L.BatchNorm(bottom, in_place=False,
                                 param=[dict(lr_mult=0, decay_mult=0), dict(lr_mult=0, decay_mult=0),
                                        dict(lr_mult=0, decay_mult=0)])
        scale = L.Scale(batch_norm, bias_term=True, in_place=True, filler=dict(value=1), bias_filler=dict(value=0))
        relu = L.ReLU(scale, in_place=inplace)
        conv = L.Convolution(relu, kernel_size=ks, stride=stride,
                             num_output=nout, pad=pad, bias_term=False, weight_filler=dict(type='xavier'),
                             bias_filler=dict(type='constant'))
        if dropout > 0:
            conv = L.Dropout(conv, dropout_ratio=dropout)
        return conv

    def add_layer(bottom, num_filter, dropout):
        conv = bn_relu_conv(bottom, ks=3, nout=num_filter, stride=1, pad=1, dropout=dropout)
        concate = L.Concat(bottom, conv, axis=1)
        return concate

    def add_bl_layer(bottom, num_filter, dropout, width):
        conv = bn_relu_conv(bottom, ks=1, nout=int(width*num_filter), stride=1, pad=0, dropout=dropout)
        conv = bn_relu_conv(conv, ks=3, nout=num_filter, stride=1, pad=1, dropout=dropout)
        concate = L.Concat(bottom, conv, axis=1)
        return concate

    def add_bl_layer2(bottom, num_filter, dropout, width):
        conv = bn_relu_conv(bottom, ks=1, nout=int(width*num_filter), stride=1, pad=0, dropout=dropout)
        conv = bn_relu_conv(conv, ks=3, nout=num_filter, stride=2, pad=1, dropout=dropout)
        conv2 = L.Pooling(bottom, pool=P.Pooling.MAX, kernel_size=2, stride=2)
        conv2 = bn_relu_conv(conv2, ks=1, nout=num_filter, stride=1, pad=0, dropout=dropout)
        concate = L.Concat(conv2, conv, axis=1)
        return concate

    def transition(bottom, num_filter, dropout):
        conv = bn_relu_conv(bottom, ks=1, nout=num_filter, stride=1, pad=0, dropout=dropout, inplace=False)
        pooling = L.Pooling(conv, pool=P.Pooling.MAX, kernel_size=2, stride=2)
        return pooling

    def transition3x3(bottom, num_filter, dropout):
        conv = bn_relu_conv(bottom, ks=3, nout=num_filter, stride=2, pad=0, dropout=dropout, inplace=False)
        # pooling = L.Pooling(conv, pool=P.Pooling.MAX, kernel_size=2, stride=2)
        return conv

    def transition_w_o_pooling(bottom, num_filter, dropout):
        conv = bn_relu_conv(bottom, ks=1, nout=num_filter, stride=1, pad=0, dropout=dropout, inplace=False)
        return conv

    first_output = 128
    growth_rate = 48
    dropout = 0
    nchannels = first_output

    assert from_layer in net.keys()

    # Stem
    model = L.Convolution(net[from_layer], kernel_size=3, stride=2, num_output=64,  # output: 150x150
                          pad=1, bias_term=False, weight_filler=dict(type='xavier'),
                          bias_filler=dict(type='constant'))

    model = L.BatchNorm(model, in_place=False, param=[dict(lr_mult=0, decay_mult=0), dict(lr_mult=0, decay_mult=0),
                                                      dict(lr_mult=0, decay_mult=0)])
    model = L.Scale(model, bias_term=True, in_place=True, filler=dict(value=1), bias_filler=dict(value=0))
    model = L.ReLU(model, in_place=True)

    model = L.Convolution(model, kernel_size=3, stride=1, num_output=64,
                          pad=1, bias_term=False, weight_filler=dict(type='xavier'),
                          bias_filler=dict(type='constant'))
    model = L.BatchNorm(model, in_place=False, param=[dict(lr_mult=0, decay_mult=0), dict(lr_mult=0, decay_mult=0),
                                                      dict(lr_mult=0, decay_mult=0)])
    model = L.Scale(model, bias_term=True, in_place=True, filler=dict(value=1), bias_filler=dict(value=0))
    model = L.ReLU(model, in_place=True)

    model = L.Convolution(model, kernel_size=3, stride=1, num_output=128,
                          pad=1, bias_term=False, weight_filler=dict(type='xavier'),
                          bias_filler=dict(type='constant'))
    model = L.BatchNorm(model, in_place=False, param=[dict(lr_mult=0, decay_mult=0), dict(lr_mult=0, decay_mult=0),
                                                      dict(lr_mult=0, decay_mult=0)])
    model = L.Scale(model, bias_term=True, in_place=True, filler=dict(value=1), bias_filler=dict(value=0))
    model = L.ReLU(model, in_place=True)
    model = L.Pooling(model, pool=P.Pooling.MAX, kernel_size=2, stride=2)  # pooling1: 75x75

    times = 1
    for i in range(6):
        model = add_bl_layer(model, growth_rate, dropout, 4)
        nchannels += growth_rate
    nchannels = int(nchannels / times)
    model = transition(model, nchannels, dropout)  # pooling2: 38x38
    for i in range(8):
        model = add_bl_layer(model, growth_rate, dropout, 4)
        nchannels += growth_rate
    nchannels = int(nchannels / times)
    model = transition_w_o_pooling(model, nchannels, dropout)  # 38x38
    net.First = model
    model1 = L.Pooling(model, pool=P.Pooling.MAX, kernel_size=2, stride=2)
    for i in range(8):
        model1 = add_bl_layer(model1, growth_rate, dropout, 4)
        nchannels += growth_rate
    nchannels = int(nchannels / times)
    model1 = transition_w_o_pooling(model1, nchannels, dropout)  # without pooling
    for i in range(8):
        model1 = add_bl_layer(model1, growth_rate, dropout, 4)
        nchannels += growth_rate
    # nchannels = int(nchannels / times)
    model1 = transition_w_o_pooling(model1, 256, dropout)  # without pooling

    f_first = L.Pooling(net.First, pool=P.Pooling.MAX, kernel_size=2, stride=2)
    f_first = bn_relu_conv(f_first, ks=1, nout=256, stride=1, pad=0, dropout=dropout)
    model1 = L.Concat(model1, f_first, axis=1)
    net.Second = model1  # pooling3: 19x19
    # name = 'Second'
    #AddExtraLayers
    model2 = add_bl_layer2(model1, 256, dropout, 1) # pooling4: 10x10
    net.Third = model2
    model3 = add_bl_layer2(model2, 128, dropout, 1) # pooling5: 5x5
    net.Fourth = model3
    model4 = add_bl_layer2(model3, 128, dropout, 1) # pooling6: 3x3
    net.Fifth = model4
    model5 = add_bl_layer2(model4, 128, dropout, 1) # pooling7: 2x2
    net.Sixth = model5
    return net

def DSOD512_V3_Body(net, from_layer):

    def bn_relu_conv(bottom, ks, nout, stride, pad, dropout, inplace=True):
        batch_norm = L.BatchNorm(bottom, in_place=False,
                                 param=[dict(lr_mult=0, decay_mult=0), dict(lr_mult=0, decay_mult=0),
                                        dict(lr_mult=0, decay_mult=0)])
        scale = L.Scale(batch_norm, bias_term=True, in_place=True, filler=dict(value=1), bias_filler=dict(value=0))
        relu = L.ReLU(scale, in_place=inplace)
        conv = L.Convolution(relu, kernel_size=ks, stride=stride,
                             num_output=nout, pad=pad, bias_term=False, weight_filler=dict(type='xavier'),
                             bias_filler=dict(type='constant'))
        if dropout > 0:
            conv = L.Dropout(conv, dropout_ratio=dropout)
        return conv

    def add_layer(bottom, num_filter, dropout):
        conv = bn_relu_conv(bottom, ks=3, nout=num_filter, stride=1, pad=1, dropout=dropout)
        concate = L.Concat(bottom, conv, axis=1)
        return concate

    def add_bl_layer(bottom, num_filter, dropout, width):
        conv = bn_relu_conv(bottom, ks=1, nout=int(width*num_filter), stride=1, pad=0, dropout=dropout)
        conv = bn_relu_conv(conv, ks=3, nout=num_filter, stride=1, pad=1, dropout=dropout)
        concate = L.Concat(bottom, conv, axis=1)
        return concate

    def add_bl_layer2(bottom, num_filter, dropout, width):
        conv = bn_relu_conv(bottom, ks=1, nout=int(width*num_filter), stride=1, pad=0, dropout=dropout)
        conv = bn_relu_conv(conv, ks=3, nout=num_filter, stride=2, pad=1, dropout=dropout)
        conv2 = L.Pooling(bottom, pool=P.Pooling.MAX, kernel_size=2, stride=2)
        conv2 = bn_relu_conv(conv2, ks=1, nout=num_filter, stride=1, pad=0, dropout=dropout)
        concate = L.Concat(conv2, conv, axis=1)
        return concate

    def transition(bottom, num_filter, dropout):
        conv = bn_relu_conv(bottom, ks=1, nout=num_filter, stride=1, pad=0, dropout=dropout, inplace=False)
        pooling = L.Pooling(conv, pool=P.Pooling.MAX, kernel_size=2, stride=2)
        return pooling

    def transition3x3(bottom, num_filter, dropout):
        conv = bn_relu_conv(bottom, ks=3, nout=num_filter, stride=2, pad=0, dropout=dropout, inplace=False)
        # pooling = L.Pooling(conv, pool=P.Pooling.MAX, kernel_size=2, stride=2)
        return conv

    def transition_w_o_pooling(bottom, num_filter, dropout):
        conv = bn_relu_conv(bottom, ks=1, nout=num_filter, stride=1, pad=0, dropout=dropout, inplace=False)
        # pooling = L.Pooling(conv, pool=P.Pooling.AVE, kernel_size=2, stride=2)
        return conv

    first_output = 128
    growth_rate = 48
    dropout = 0
    nchannels = first_output

    assert from_layer in net.keys()
    # Stem
    model = L.Convolution(net[from_layer], kernel_size=3, stride=2, num_output=64,  # output: 256x256
                          pad=1, bias_term=False, weight_filler=dict(type='xavier'),
                          bias_filler=dict(type='constant'))

    model = L.BatchNorm(model, in_place=False, param=[dict(lr_mult=0, decay_mult=0), dict(lr_mult=0, decay_mult=0),
                                                      dict(lr_mult=0, decay_mult=0)])
    model = L.Scale(model, bias_term=True, in_place=True, filler=dict(value=1), bias_filler=dict(value=0))
    model = L.ReLU(model, in_place=True)

    model = L.Convolution(model, kernel_size=3, stride=1, num_output=64,
                          pad=1, bias_term=False, weight_filler=dict(type='xavier'),
                          bias_filler=dict(type='constant'))
    model = L.BatchNorm(model, in_place=False, param=[dict(lr_mult=0, decay_mult=0), dict(lr_mult=0, decay_mult=0),
                                                      dict(lr_mult=0, decay_mult=0)])
    model = L.Scale(model, bias_term=True, in_place=True, filler=dict(value=1), bias_filler=dict(value=0))
    model = L.ReLU(model, in_place=True)

    model = L.Convolution(model, kernel_size=3, stride=1, num_output=128,
                          pad=1, bias_term=False, weight_filler=dict(type='xavier'),
                          bias_filler=dict(type='constant'))
    model = L.BatchNorm(model, in_place=False, param=[dict(lr_mult=0, decay_mult=0), dict(lr_mult=0, decay_mult=0),
                                                      dict(lr_mult=0, decay_mult=0)])
    model = L.Scale(model, bias_term=True, in_place=True, filler=dict(value=1), bias_filler=dict(value=0))
    model = L.ReLU(model, in_place=True)
    model = L.Pooling(model, pool=P.Pooling.MAX, kernel_size=2, stride=2)  # pooling1: 128x128

    times = 1
    for i in range(6):
        model = add_bl_layer(model, growth_rate, dropout, 4)
        nchannels += growth_rate
    nchannels = int(nchannels / times)
    model = transition(model, nchannels, dropout)  # pooling2: 64x64
    for i in range(8):
        model = add_bl_layer(model, growth_rate, dropout, 4)
        nchannels += growth_rate
    nchannels = int(nchannels / times)
    model = transition_w_o_pooling(model, nchannels, dropout)  # 64x64
    net.First = model
    model1 = L.Pooling(model, pool=P.Pooling.MAX, kernel_size=2, stride=2)
    for i in range(8):
        model1 = add_bl_layer(model1, growth_rate, dropout, 4)
        nchannels += growth_rate
    nchannels = int(nchannels / times)
    model1 = transition_w_o_pooling(model1, nchannels, dropout)  # without pooling

    for i in range(8):
        model1 = add_bl_layer(model1, growth_rate, dropout, 4)
        nchannels += growth_rate
    # nchannels = int(nchannels / times)
    model1 = transition_w_o_pooling(model1, 256, dropout)  # without pooling

    f_first = L.Pooling(net.First, pool=P.Pooling.MAX, kernel_size=2, stride=2)
    f_first = bn_relu_conv(f_first, ks=1, nout=256, stride=1, pad=0, dropout=dropout)
    model1 = L.Concat(model1, f_first, axis=1)
    net.Second = model1  # pooling3: 32x32
    # name = 'Second'
    #AddExtraLayers
    model2 = add_bl_layer2(model1, 256, dropout, 1)# pooling4: 16x16
    net.Third = model2
    model3 = add_bl_layer2(model2, 128, dropout, 1)# pooling5: 8x8
    net.Fourth = model3
    model4 = add_bl_layer2(model3, 128, dropout, 1)# pooling6: 4x4
    net.Fifth_ = model4
    model5 = add_bl_layer2(model4, 128, dropout, 1) # pooling7: 2x2
    net.Sixth_ = model5
    model6 = add_bl_layer2(model5, 128, dropout, 1) # pooling8: 1x1
    net.Seventh_ = model6
    return net

def GRP_DSOD320_V6_Recurrent_Pyramid(net, from_layer):

    def conv_bn_relu(bottom, ks, nout, stride, pad, dropout, inplace=True):
        conv = L.Convolution(bottom, kernel_size=ks, stride=stride,
                       num_output=nout, pad=pad, bias_term=False, weight_filler=dict(type='xavier'),
                       bias_filler=dict(type='constant'))
        batch_norm = L.BatchNorm(conv, in_place=True, batch_norm_param = dict(eps = 1e-4),
                                 param=[dict(lr_mult=0, decay_mult=0), dict(lr_mult=0, decay_mult=0),
                                        dict(lr_mult=0, decay_mult=0)])
        scale = L.Scale(batch_norm, bias_term=True, in_place=True, filler=dict(value=1), bias_filler=dict(value=0))
        relu = L.ReLU(scale, in_place=True)
        if dropout > 0:
            conv = L.Dropout(relu, dropout_ratio=dropout)
        return relu

    def deconv(bottom, ks, nout, stride, dropout, inplace=True):
        deconv = L.Deconvolution(bottom, convolution_param=dict(num_output=nout, kernel_size=ks, stride=stride,
                                bias_term=False, weight_filler=dict(type='bilinear')), param=[dict(lr_mult=0, decay_mult=0)])
        batch_norm = L.BatchNorm(deconv, in_place=True, batch_norm_param = dict(eps = 1e-4),
                         param=[dict(lr_mult=0, decay_mult=0), dict(lr_mult=0, decay_mult=0),
                                dict(lr_mult=0, decay_mult=0)])
        scale = L.Scale(batch_norm, bias_term=True, in_place=True, filler=dict(value=1), bias_filler=dict(value=0))
        relu = L.ReLU(scale, in_place=True)
        if dropout > 0:
            conv = L.Dropout(relu, dropout_ratio=dropout)
        return relu

    def dilation_conv(bottom, ks, nout, stride, pad, dropout, dilation, inplace=True):
        conv = L.Convolution(bottom, kernel_size=ks, stride=stride,
                       num_output=nout, pad=pad, dilation=dilation, bias_term=False, weight_filler=dict(type='xavier'),
                       bias_filler=dict(type='constant'))
        batch_norm = L.BatchNorm(conv, in_place=True, batch_norm_param = dict(eps = 1e-4),
                                 param=[dict(lr_mult=0, decay_mult=0), dict(lr_mult=0, decay_mult=0),
                                        dict(lr_mult=0, decay_mult=0)])
        scale = L.Scale(batch_norm, bias_term=True, in_place=True, filler=dict(value=1), bias_filler=dict(value=0))
        relu = L.ReLU(scale, in_place=True)
        if dropout > 0:
            conv = L.Dropout(relu, dropout_ratio=dropout)
        return relu

    def add_recurrent_layer(bottom, ks, num_filter, dropout):
        # conv = conv_bn_relu(bottom, ks=1, nout=int(width*num_filter), stride=1, pad=0, dropout=dropout)
        # conv = conv_bn_relu(conv, ks=3, nout=num_filter, stride=2, pad=1, dropout=dropout)  # new conv
        # conv2 = L.Pooling(bottom, pool=P.Pooling.MAX, kernel_size=2, stride=2)
        # conv2 = conv_bn_relu(conv2, ks=1, nout=num_filter, stride=1, pad=0, dropout=dropout)  # previous conv
        extra_de = deconv(bottom, ks=ks, nout=num_filter, stride=2, dropout=dropout)  # later conv
        # concate = L.concate(conv, conv2, extra_de, axis=1)
        return extra_de

    def add_layer(bottom, num_filter, dropout):
        conv = conv_bn_relu(bottom, ks=3, nout=num_filter, stride=1, pad=1, dropout=dropout)
        concate = L.Concat(bottom, conv, axis=1)
        return concate

    def add_bl_layer(bottom, num_filter, dropout, width):
        conv = conv_bn_relu(bottom, ks=1, nout=int(width*num_filter), stride=1, pad=0, dropout=dropout)
        conv = conv_bn_relu(conv, ks=3, nout=num_filter, stride=1, pad=1, dropout=dropout)
        concate = L.Concat(bottom, conv, axis=1)
        return concate

    def add_bl_layer2(bottom, num_filter, dropout, width):
        conv = conv_bn_relu(bottom, ks=1, nout=int(width*num_filter), stride=1, pad=0, dropout=dropout)
        conv = conv_bn_relu(conv, ks=3, nout=num_filter, stride=2, pad=1, dropout=dropout)
        conv2 = L.Pooling(bottom, pool=P.Pooling.MAX, kernel_size=2, stride=2)
        conv2 = conv_bn_relu(conv2, ks=1, nout=num_filter, stride=1, pad=0, dropout=dropout)
        concate = L.Concat(conv2, conv, axis=1)
        return concate

    def transition(bottom, num_filter, dropout):
        conv = conv_bn_relu(bottom, ks=1, nout=num_filter, stride=1, pad=0, dropout=dropout, inplace=False)
        pooling = L.Pooling(bottom, pool=P.Pooling.MAX, kernel_size=2, stride=2)
        return pooling

    def transition3x3(bottom, num_filter, dropout):
        conv = conv_bn_relu(bottom, ks=3, nout=num_filter, stride=2, pad=0, dropout=dropout, inplace=False)
        # pooling = L.Pooling(conv, pool=P.Pooling.MAX, kernel_size=2, stride=2)
        return conv

    def transition_w_o_pooling(bottom, num_filter, dropout):
        conv = conv_bn_relu(bottom, ks=1, nout=num_filter, stride=1, pad=0, dropout=dropout, inplace=False)
        return conv

    first_output = 128
    growth_rate = 48
    dropout = 0.0
    nchannels = first_output

    assert from_layer in net.keys()

    # Stem
    model = L.Convolution(net[from_layer], kernel_size=3, stride=2, num_output=64,  # output: 16x160
                          pad=1, bias_term=False, weight_filler=dict(type='xavier'),
                          bias_filler=dict(type='constant'))
    model = L.BatchNorm(model, in_place=True, batch_norm_param = dict(eps = 1e-4),
                           param=[dict(lr_mult=0, decay_mult=0), dict(lr_mult=0, decay_mult=0),
                                  dict(lr_mult=0, decay_mult=0)])
    model = L.Scale(model, bias_term=True, in_place=True, filler=dict(value=1), bias_filler=dict(value=0))
    model = L.ReLU(model, in_place=True)

    model = L.Convolution(model, kernel_size=3, stride=1, num_output=64,
                          pad=1, bias_term=False, weight_filler=dict(type='xavier'),
                          bias_filler=dict(type='constant'))
    model = L.BatchNorm(model, in_place=True, batch_norm_param = dict(eps = 1e-4),
                           param=[dict(lr_mult=0, decay_mult=0), dict(lr_mult=0, decay_mult=0),
                                  dict(lr_mult=0, decay_mult=0)])
    model = L.Scale(model, bias_term=True, in_place=True, filler=dict(value=1), bias_filler=dict(value=0))
    model = L.ReLU(model, in_place=True)

    model = L.Convolution(model, kernel_size=3, stride=1, num_output=128,
                          pad=1, bias_term=False, weight_filler=dict(type='xavier'),
                          bias_filler=dict(type='constant'))
    model = L.BatchNorm(model, in_place=True, batch_norm_param = dict(eps = 1e-4),
                           param=[dict(lr_mult=0, decay_mult=0), dict(lr_mult=0, decay_mult=0),
                                  dict(lr_mult=0, decay_mult=0)])
    model = L.Scale(model, bias_term=True, in_place=True, filler=dict(value=1), bias_filler=dict(value=0))
    model = L.ReLU(model, in_place=True)
    model0 = L.Pooling(model, pool=P.Pooling.MAX, kernel_size=2, stride=2)  # pooling1: 80x80

    times = 1

    for i in range(6):
        model0 = add_bl_layer(model0, growth_rate, dropout, 4)
        nchannels += growth_rate
    nchannels = int(nchannels / times)
    model0 = transition_w_o_pooling(model0, nchannels, dropout)  # 80x80

    model1 = L.Pooling(model0, pool=P.Pooling.MAX, kernel_size=2, stride=2)  # 40x40
    for i in range(8):
        model1 = add_bl_layer(model1, growth_rate, dropout, 4)
        nchannels += growth_rate
    nchannels = int(nchannels / times)
    model1 = transition_w_o_pooling(model1, nchannels, dropout)  # 40x40

    f_extra0 = L.Pooling(model, pool=P.Pooling.MAX, kernel_size=4, stride=4)
    f_extra0 = conv_bn_relu(f_extra0, ks=1, nout=128, stride=1, pad=0, dropout=dropout)
    f_extra1 = L.Pooling(model0, pool=P.Pooling.MAX, kernel_size=2, stride=2)
    f_extra1 = conv_bn_relu(f_extra1, ks=1, nout=128, stride=1, pad=0, dropout=dropout)
    Concat1 = L.Concat(model1, f_extra0, f_extra1, axis=1)
    net.First = Concat1 #  40x40

    model2 = L.Pooling(model1, pool=P.Pooling.MAX, kernel_size=2, stride=2)
    for i in range(8):
        model2 = add_bl_layer(model2, growth_rate, dropout, 4)
        nchannels += growth_rate
    nchannels = int(nchannels / times)
    model2 = transition_w_o_pooling(model2, nchannels, dropout)  # without pooling
    for i in range(8):
        model2 = add_bl_layer(model2, growth_rate, dropout, 4)
        nchannels += growth_rate
    # nchannels = int(nchannels / times)
    model2 = transition_w_o_pooling(model2, 171, dropout)  # without pooling

    f_first = L.Pooling(net.First, pool=P.Pooling.MAX, kernel_size=2, stride=2)
    f_first = conv_bn_relu(f_first, ks=1, nout=171, stride=1, pad=0, dropout=dropout)
    model2 = L.Concat(model2, f_first, axis=1)
    net.Second = model2  # pooling3: 20x20
    # name = 'Second'
    #AddExtraLayers
    model3 = add_bl_layer2(model2, 86, dropout, 1) # pooling4: 10x10
    net.Third = model3
    model4 = add_bl_layer2(model3, 86, dropout, 1) # pooling5: 5x5
    net.Fourth = model4
    model5 = add_bl_layer2(model4, 86, dropout, 1) # pooling6: 3x3
    net.Fifth = model5
    model6 = add_bl_layer2(model5, 128, dropout, 1) # pooling7: 2x2
    net.Sixth = model6

    # AddRecurrentLayers
    # # 300x300
  
    # ks = 2
    # Recurrent1 = add_recurrent_layer(model2, ks, 128, dropout)  # 38x38
    # net.Recurrent1 = L.Concat(Recurrent1, Concat1, axis=1)  
    # ks=1
    # Recurrent2 = add_recurrent_layer(model3, ks, 171, dropout)    # 19x19
    # net.Recurrent2 = L.Concat(Recurrent2, model2, axis=1)  
    # ks=2
    # Recurrent3 = add_recurrent_layer(model4, ks, 86, dropout)    # 10x10
    # net.Recurrent3 = L.Concat(Recurrent3, model3, axis=1)
    # ks=1
    # Recurrent4 = add_recurrent_layer(model5, ks, 86, dropout)    # 5x5
    # net.Recurrent4 = L.Concat(Recurrent4, model4, axis=1)
    # ks=1
    # Recurrent5 = add_recurrent_layer(model6, ks, 86, dropout)    # 3x3
    # net.Recurrent5 = L.Concat(Recurrent5, model5, axis=1)
    # net.Recurrent6 = model6

    # 320x320
    ks = 2
    Recurrent1 = add_recurrent_layer(model2, ks, 128, dropout)  # 40x40
    net.Recurrent1 = L.Concat(Recurrent1, Concat1, axis=1)  
    ks=2
    Recurrent2 = add_recurrent_layer(model3, ks, 171, dropout)    # 20x20
    net.Recurrent2 = L.Concat(Recurrent2, model2, axis=1)  
    ks=2
    Recurrent3 = add_recurrent_layer(model4, ks, 86, dropout)    # 10x10
    net.Recurrent3 = L.Concat(Recurrent3, model3, axis=1)
    ks=1
    Recurrent4 = add_recurrent_layer(model5, ks, 86, dropout)    # 5x5
    net.Recurrent4 = L.Concat(Recurrent4, model4, axis=1)
    ks=1
    Recurrent5 = add_recurrent_layer(model6, ks, 86, dropout)    # 3x3
    net.Recurrent5 = L.Concat(Recurrent5, model5, axis=1)
    net.Recurrent6 = model6

    return net

def Gated_module(net, channel_nums=[], from_layers=[]):
    def channel_level(net, from_layer, channel_num, relu_name):
        fc = L.InnerProduct(net[relu_name], num_output=int(channel_num))
        sigmoid = L.Sigmoid(fc, in_place=True)
        scale = L.Scale(net[from_layer], sigmoid, axis=0, bias_term=False, bias_filler=dict(value=0))
        relu = L.ReLU(scale, in_place=True)
        att_name = "{}_att".format(from_layer)
        net[att_name] = relu
        return net

    def global_level(net, from_layer, relu_name):
        fc = L.InnerProduct(net[relu_name], num_output=1)
        sigmoid = L.Sigmoid(fc, in_place=True)
        att_name = "{}_att".format(from_layer)
        sigmoid = L.Reshape(sigmoid, reshape_param=dict(shape=dict(dim=[-1])))
        scale = L.Scale(net[att_name], sigmoid, axis=0, bias_term=False, bias_filler=dict(value=0))
        # relu = L.ReLU(scale, in_place=True)
        residual = L.Eltwise(net[from_layer], scale)
        gatt_name = "{}_gate".format(from_layer)
        net[gatt_name] = residual
        return net

    num = len(from_layers)
    for i in range(0, num):
        from_layer = from_layers[i]
        channel_num = channel_nums[i]
        # shared params
        gate_name = "{}_gate".format(from_layer)
        pool_name = "{}_pool".format(from_layer)
        fc_name = "{}_fc".format(from_layer)
        relu_name = "{}_relu".format(from_layer)
        net[pool_name] = L.Pooling(net[from_layer], pool=P.Pooling.AVE, global_pooling=True)
        net[fc_name] = L.InnerProduct(net[pool_name], num_output=int(channel_num/16.0))
        net[relu_name] = L.ReLU(net[fc_name], in_place=True)
        net = channel_level(net, from_layer, channel_num, relu_name)
        net = global_level(net, from_layer, relu_name)

    return net

def ResNet101Body(net, from_layer, use_pool5=True, use_dilation_conv5=False, **bn_param):
    conv_prefix = ''
    conv_postfix = ''
    bn_prefix = 'bn_'
    bn_postfix = ''
    scale_prefix = 'scale_'
    scale_postfix = ''
    ConvBNLayer(net, from_layer, 'conv1', use_bn=True, use_relu=True,
        num_output=64, kernel_size=7, pad=3, stride=2,
        conv_prefix=conv_prefix, conv_postfix=conv_postfix,
        bn_prefix=bn_prefix, bn_postfix=bn_postfix,
        scale_prefix=scale_prefix, scale_postfix=scale_postfix, **bn_param)

    net.pool1 = L.Pooling(net.conv1, pool=P.Pooling.MAX, kernel_size=3, stride=2)

    ResBody(net, 'pool1', '2a', out2a=64, out2b=64, out2c=256, stride=1, use_branch1=True, **bn_param)
    ResBody(net, 'res2a', '2b', out2a=64, out2b=64, out2c=256, stride=1, use_branch1=False, **bn_param)
    ResBody(net, 'res2b', '2c', out2a=64, out2b=64, out2c=256, stride=1, use_branch1=False, **bn_param)

    ResBody(net, 'res2c', '3a', out2a=128, out2b=128, out2c=512, stride=2, use_branch1=True, **bn_param)

    from_layer = 'res3a'
    for i in xrange(1, 4):
      block_name = '3b{}'.format(i)
      ResBody(net, from_layer, block_name, out2a=128, out2b=128, out2c=512, stride=1, use_branch1=False, **bn_param)
      from_layer = 'res{}'.format(block_name)

    ResBody(net, from_layer, '4a', out2a=256, out2b=256, out2c=1024, stride=2, use_branch1=True, **bn_param)

    from_layer = 'res4a'
    for i in xrange(1, 23):
      block_name = '4b{}'.format(i)
      ResBody(net, from_layer, block_name, out2a=256, out2b=256, out2c=1024, stride=1, use_branch1=False, **bn_param)
      from_layer = 'res{}'.format(block_name)

    stride = 2
    dilation = 1
    if use_dilation_conv5:
      stride = 1
      dilation = 2

    ResBody(net, from_layer, '5a', out2a=512, out2b=512, out2c=2048, stride=stride, use_branch1=True, dilation=dilation, **bn_param)
    ResBody(net, 'res5a', '5b', out2a=512, out2b=512, out2c=2048, stride=1, use_branch1=False, dilation=dilation, **bn_param)
    ResBody(net, 'res5b', '5c', out2a=512, out2b=512, out2c=2048, stride=1, use_branch1=False, dilation=dilation, **bn_param)

    if use_pool5:
      net.pool5 = L.Pooling(net.res5c, pool=P.Pooling.AVE, global_pooling=True)

    return net

def ResNet152Body(net, from_layer, use_pool5=True, use_dilation_conv5=False, **bn_param):
    conv_prefix = ''
    conv_postfix = ''
    bn_prefix = 'bn_'
    bn_postfix = ''
    scale_prefix = 'scale_'
    scale_postfix = ''
    ConvBNLayer(net, from_layer, 'conv1', use_bn=True, use_relu=True,
        num_output=64, kernel_size=7, pad=3, stride=2,
        conv_prefix=conv_prefix, conv_postfix=conv_postfix,
        bn_prefix=bn_prefix, bn_postfix=bn_postfix,
        scale_prefix=scale_prefix, scale_postfix=scale_postfix, **bn_param)

    net.pool1 = L.Pooling(net.conv1, pool=P.Pooling.MAX, kernel_size=3, stride=2)

    ResBody(net, 'pool1', '2a', out2a=64, out2b=64, out2c=256, stride=1, use_branch1=True, **bn_param)
    ResBody(net, 'res2a', '2b', out2a=64, out2b=64, out2c=256, stride=1, use_branch1=False, **bn_param)
    ResBody(net, 'res2b', '2c', out2a=64, out2b=64, out2c=256, stride=1, use_branch1=False, **bn_param)

    ResBody(net, 'res2c', '3a', out2a=128, out2b=128, out2c=512, stride=2, use_branch1=True, **bn_param)

    from_layer = 'res3a'
    for i in xrange(1, 8):
      block_name = '3b{}'.format(i)
      ResBody(net, from_layer, block_name, out2a=128, out2b=128, out2c=512, stride=1, use_branch1=False, **bn_param)
      from_layer = 'res{}'.format(block_name)

    ResBody(net, from_layer, '4a', out2a=256, out2b=256, out2c=1024, stride=2, use_branch1=True, **bn_param)

    from_layer = 'res4a'
    for i in xrange(1, 36):
      block_name = '4b{}'.format(i)
      ResBody(net, from_layer, block_name, out2a=256, out2b=256, out2c=1024, stride=1, use_branch1=False, **bn_param)
      from_layer = 'res{}'.format(block_name)

    stride = 2
    dilation = 1
    if use_dilation_conv5:
      stride = 1
      dilation = 2

    ResBody(net, from_layer, '5a', out2a=512, out2b=512, out2c=2048, stride=stride, use_branch1=True, dilation=dilation, **bn_param)
    ResBody(net, 'res5a', '5b', out2a=512, out2b=512, out2c=2048, stride=1, use_branch1=False, dilation=dilation, **bn_param)
    ResBody(net, 'res5b', '5c', out2a=512, out2b=512, out2c=2048, stride=1, use_branch1=False, dilation=dilation, **bn_param)

    if use_pool5:
      net.pool5 = L.Pooling(net.res5c, pool=P.Pooling.AVE, global_pooling=True)

    return net

def InceptionV3Body(net, from_layer, output_pred=False, **bn_param):
  # scale is fixed to 1, thus we ignore it.
  use_scale = False

  out_layer = 'conv'
  ConvBNLayer(net, from_layer, out_layer, use_bn=True, use_relu=True,
      num_output=32, kernel_size=3, pad=0, stride=2, use_scale=use_scale,
      **bn_param)
  from_layer = out_layer

  out_layer = 'conv_1'
  ConvBNLayer(net, from_layer, out_layer, use_bn=True, use_relu=True,
      num_output=32, kernel_size=3, pad=0, stride=1, use_scale=use_scale,
      **bn_param)
  from_layer = out_layer

  out_layer = 'conv_2'
  ConvBNLayer(net, from_layer, out_layer, use_bn=True, use_relu=True,
      num_output=64, kernel_size=3, pad=1, stride=1, use_scale=use_scale,
      **bn_param)
  from_layer = out_layer

  out_layer = 'pool'
  net[out_layer] = L.Pooling(net[from_layer], pool=P.Pooling.MAX,
      kernel_size=3, stride=2, pad=0)
  from_layer = out_layer

  out_layer = 'conv_3'
  ConvBNLayer(net, from_layer, out_layer, use_bn=True, use_relu=True,
      num_output=80, kernel_size=1, pad=0, stride=1, use_scale=use_scale,
      **bn_param)
  from_layer = out_layer

  out_layer = 'conv_4'
  ConvBNLayer(net, from_layer, out_layer, use_bn=True, use_relu=True,
      num_output=192, kernel_size=3, pad=0, stride=1, use_scale=use_scale,
      **bn_param)
  from_layer = out_layer

  out_layer = 'pool_1'
  net[out_layer] = L.Pooling(net[from_layer], pool=P.Pooling.MAX,
      kernel_size=3, stride=2, pad=0)
  from_layer = out_layer

  # inceptions with 1x1, 3x3, 5x5 convolutions
  for inception_id in xrange(0, 3):
    if inception_id == 0:
      out_layer = 'mixed'
      tower_2_conv_num_output = 32
    else:
      out_layer = 'mixed_{}'.format(inception_id)
      tower_2_conv_num_output = 64
    towers = []
    tower_name = '{}'.format(out_layer)
    tower = InceptionTower(net, from_layer, tower_name, [
        dict(name='conv', num_output=64, kernel_size=1, pad=0, stride=1),
        ], **bn_param)
    towers.append(tower)
    tower_name = '{}/tower'.format(out_layer)
    tower = InceptionTower(net, from_layer, tower_name, [
        dict(name='conv', num_output=48, kernel_size=1, pad=0, stride=1),
        dict(name='conv_1', num_output=64, kernel_size=5, pad=2, stride=1),
        ], **bn_param)
    towers.append(tower)
    tower_name = '{}/tower_1'.format(out_layer)
    tower = InceptionTower(net, from_layer, tower_name, [
        dict(name='conv', num_output=64, kernel_size=1, pad=0, stride=1),
        dict(name='conv_1', num_output=96, kernel_size=3, pad=1, stride=1),
        dict(name='conv_2', num_output=96, kernel_size=3, pad=1, stride=1),
        ], **bn_param)
    towers.append(tower)
    tower_name = '{}/tower_2'.format(out_layer)
    tower = InceptionTower(net, from_layer, tower_name, [
        dict(name='pool', pool=P.Pooling.AVE, kernel_size=3, pad=1, stride=1),
        dict(name='conv', num_output=tower_2_conv_num_output, kernel_size=1, pad=0, stride=1),
        ], **bn_param)
    towers.append(tower)
    out_layer = '{}/join'.format(out_layer)
    net[out_layer] = L.Concat(*towers, axis=1)
    from_layer = out_layer

  # inceptions with 1x1, 3x3(in sequence) convolutions
  out_layer = 'mixed_3'
  towers = []
  tower_name = '{}'.format(out_layer)
  tower = InceptionTower(net, from_layer, tower_name, [
      dict(name='conv', num_output=384, kernel_size=3, pad=0, stride=2),
      ], **bn_param)
  towers.append(tower)
  tower_name = '{}/tower'.format(out_layer)
  tower = InceptionTower(net, from_layer, tower_name, [
      dict(name='conv', num_output=64, kernel_size=1, pad=0, stride=1),
      dict(name='conv_1', num_output=96, kernel_size=3, pad=1, stride=1),
      dict(name='conv_2', num_output=96, kernel_size=3, pad=0, stride=2),
      ], **bn_param)
  towers.append(tower)
  tower_name = '{}'.format(out_layer)
  tower = InceptionTower(net, from_layer, tower_name, [
      dict(name='pool', pool=P.Pooling.MAX, kernel_size=3, pad=0, stride=2),
      ], **bn_param)
  towers.append(tower)
  out_layer = '{}/join'.format(out_layer)
  net[out_layer] = L.Concat(*towers, axis=1)
  from_layer = out_layer

  # inceptions with 1x1, 7x1, 1x7 convolutions
  for inception_id in xrange(4, 8):
    if inception_id == 4:
      num_output = 128
    elif inception_id == 5 or inception_id == 6:
      num_output = 160
    elif inception_id == 7:
      num_output = 192
    out_layer = 'mixed_{}'.format(inception_id)
    towers = []
    tower_name = '{}'.format(out_layer)
    tower = InceptionTower(net, from_layer, tower_name, [
        dict(name='conv', num_output=192, kernel_size=1, pad=0, stride=1),
        ], **bn_param)
    towers.append(tower)
    tower_name = '{}/tower'.format(out_layer)
    tower = InceptionTower(net, from_layer, tower_name, [
        dict(name='conv', num_output=num_output, kernel_size=1, pad=0, stride=1),
        dict(name='conv_1', num_output=num_output, kernel_size=[1, 7], pad=[0, 3], stride=[1, 1]),
        dict(name='conv_2', num_output=192, kernel_size=[7, 1], pad=[3, 0], stride=[1, 1]),
        ], **bn_param)
    towers.append(tower)
    tower_name = '{}/tower_1'.format(out_layer)
    tower = InceptionTower(net, from_layer, tower_name, [
        dict(name='conv', num_output=num_output, kernel_size=1, pad=0, stride=1),
        dict(name='conv_1', num_output=num_output, kernel_size=[7, 1], pad=[3, 0], stride=[1, 1]),
        dict(name='conv_2', num_output=num_output, kernel_size=[1, 7], pad=[0, 3], stride=[1, 1]),
        dict(name='conv_3', num_output=num_output, kernel_size=[7, 1], pad=[3, 0], stride=[1, 1]),
        dict(name='conv_4', num_output=192, kernel_size=[1, 7], pad=[0, 3], stride=[1, 1]),
        ], **bn_param)
    towers.append(tower)
    tower_name = '{}/tower_2'.format(out_layer)
    tower = InceptionTower(net, from_layer, tower_name, [
        dict(name='pool', pool=P.Pooling.AVE, kernel_size=3, pad=1, stride=1),
        dict(name='conv', num_output=192, kernel_size=1, pad=0, stride=1),
        ], **bn_param)
    towers.append(tower)
    out_layer = '{}/join'.format(out_layer)
    net[out_layer] = L.Concat(*towers, axis=1)
    from_layer = out_layer

  # inceptions with 1x1, 3x3, 1x7, 7x1 filters
  out_layer = 'mixed_8'
  towers = []
  tower_name = '{}/tower'.format(out_layer)
  tower = InceptionTower(net, from_layer, tower_name, [
      dict(name='conv', num_output=192, kernel_size=1, pad=0, stride=1),
      dict(name='conv_1', num_output=320, kernel_size=3, pad=0, stride=2),
      ], **bn_param)
  towers.append(tower)
  tower_name = '{}/tower_1'.format(out_layer)
  tower = InceptionTower(net, from_layer, tower_name, [
      dict(name='conv', num_output=192, kernel_size=1, pad=0, stride=1),
      dict(name='conv_1', num_output=192, kernel_size=[1, 7], pad=[0, 3], stride=[1, 1]),
      dict(name='conv_2', num_output=192, kernel_size=[7, 1], pad=[3, 0], stride=[1, 1]),
      dict(name='conv_3', num_output=192, kernel_size=3, pad=0, stride=2),
      ], **bn_param)
  towers.append(tower)
  tower_name = '{}'.format(out_layer)
  tower = InceptionTower(net, from_layer, tower_name, [
      dict(name='pool', pool=P.Pooling.MAX, kernel_size=3, pad=0, stride=2),
      ], **bn_param)
  towers.append(tower)
  out_layer = '{}/join'.format(out_layer)
  net[out_layer] = L.Concat(*towers, axis=1)
  from_layer = out_layer

  for inception_id in xrange(9, 11):
    num_output = 384
    num_output2 = 448
    if inception_id == 9:
      pool = P.Pooling.AVE
    else:
      pool = P.Pooling.MAX
    out_layer = 'mixed_{}'.format(inception_id)
    towers = []
    tower_name = '{}'.format(out_layer)
    tower = InceptionTower(net, from_layer, tower_name, [
        dict(name='conv', num_output=320, kernel_size=1, pad=0, stride=1),
        ], **bn_param)
    towers.append(tower)

    tower_name = '{}/tower'.format(out_layer)
    tower = InceptionTower(net, from_layer, tower_name, [
        dict(name='conv', num_output=num_output, kernel_size=1, pad=0, stride=1),
        ], **bn_param)
    subtowers = []
    subtower_name = '{}/mixed'.format(tower_name)
    subtower = InceptionTower(net, '{}/conv'.format(tower_name), subtower_name, [
        dict(name='conv', num_output=num_output, kernel_size=[1, 3], pad=[0, 1], stride=[1, 1]),
        ], **bn_param)
    subtowers.append(subtower)
    subtower = InceptionTower(net, '{}/conv'.format(tower_name), subtower_name, [
        dict(name='conv_1', num_output=num_output, kernel_size=[3, 1], pad=[1, 0], stride=[1, 1]),
        ], **bn_param)
    subtowers.append(subtower)
    net[subtower_name] = L.Concat(*subtowers, axis=1)
    towers.append(net[subtower_name])

    tower_name = '{}/tower_1'.format(out_layer)
    tower = InceptionTower(net, from_layer, tower_name, [
        dict(name='conv', num_output=num_output2, kernel_size=1, pad=0, stride=1),
        dict(name='conv_1', num_output=num_output, kernel_size=3, pad=1, stride=1),
        ], **bn_param)
    subtowers = []
    subtower_name = '{}/mixed'.format(tower_name)
    subtower = InceptionTower(net, '{}/conv_1'.format(tower_name), subtower_name, [
        dict(name='conv', num_output=num_output, kernel_size=[1, 3], pad=[0, 1], stride=[1, 1]),
        ], **bn_param)
    subtowers.append(subtower)
    subtower = InceptionTower(net, '{}/conv_1'.format(tower_name), subtower_name, [
        dict(name='conv_1', num_output=num_output, kernel_size=[3, 1], pad=[1, 0], stride=[1, 1]),
        ], **bn_param)
    subtowers.append(subtower)
    net[subtower_name] = L.Concat(*subtowers, axis=1)
    towers.append(net[subtower_name])

    tower_name = '{}/tower_2'.format(out_layer)
    tower = InceptionTower(net, from_layer, tower_name, [
        dict(name='pool', pool=pool, kernel_size=3, pad=1, stride=1),
        dict(name='conv', num_output=192, kernel_size=1, pad=0, stride=1),
        ], **bn_param)
    towers.append(tower)
    out_layer = '{}/join'.format(out_layer)
    net[out_layer] = L.Concat(*towers, axis=1)
    from_layer = out_layer

  if output_pred:
    net.pool_3 = L.Pooling(net[from_layer], pool=P.Pooling.AVE, kernel_size=8, pad=0, stride=1)
    net.softmax = L.InnerProduct(net.pool_3, num_output=1008)
    net.softmax_prob = L.Softmax(net.softmax)

  return net

def CreateMultiBoxHead(net, data_layer="data", num_classes=[], from_layers=[],
        use_objectness=False, normalizations=[], use_batchnorm=True, lr_mult=1,
        use_scale=True, min_sizes=[], max_sizes=[], prior_variance = [0.1],
        aspect_ratios=[], steps=[], img_height=0, img_width=0, share_location=True,
        flip=True, clip=True, offset=0.5, inter_layer_depth=[], kernel_size=1, pad=0,
        conf_postfix='', loc_postfix='', **bn_param):
    assert num_classes, "must provide num_classes"
    assert num_classes > 0, "num_classes must be positive number"
    if normalizations:
        assert len(from_layers) == len(normalizations), "from_layers and normalizations should have same length"
    assert len(from_layers) == len(min_sizes), "from_layers and min_sizes should have same length"
    if max_sizes:
        assert len(from_layers) == len(max_sizes), "from_layers and max_sizes should have same length"
    if aspect_ratios:
        assert len(from_layers) == len(aspect_ratios), "from_layers and aspect_ratios should have same length"
    if steps:
        assert len(from_layers) == len(steps), "from_layers and steps should have same length"
    net_layers = net.keys()
    assert data_layer in net_layers, "data_layer is not in net's layers"
    if inter_layer_depth:
        assert len(from_layers) == len(inter_layer_depth), "from_layers and inter_layer_depth should have same length"

    num = len(from_layers)
    priorbox_layers = []
    loc_layers = []
    conf_layers = []
    objectness_layers = []
    for i in range(0, num):
        from_layer = from_layers[i]

        # Get the normalize value.
        if normalizations:
            if normalizations[i] != -1:
                norm_name = "{}_norm".format(from_layer)
                net[norm_name] = L.Normalize(net[from_layer], scale_filler=dict(type="constant", value=normalizations[i]),
                    across_spatial=False, channel_shared=False)
                from_layer = norm_name

        # Add intermediate layers.
        if inter_layer_depth:
            if inter_layer_depth[i] > 0:
                inter_name = "{}_inter".format(from_layer)
                ConvBNLayer(net, from_layer, inter_name, use_bn=use_batchnorm, use_relu=True, lr_mult=lr_mult,
                      num_output=inter_layer_depth[i], kernel_size=3, pad=1, stride=1, **bn_param)
                from_layer = inter_name

        # Estimate number of priors per location given provided parameters.
        min_size = min_sizes[i]
        if type(min_size) is not list:
            min_size = [min_size]
        aspect_ratio = []
        if len(aspect_ratios) > i:
            aspect_ratio = aspect_ratios[i]
            if type(aspect_ratio) is not list:
                aspect_ratio = [aspect_ratio]
        max_size = []
        if len(max_sizes) > i:
            max_size = max_sizes[i]
            if type(max_size) is not list:
                max_size = [max_size]
            if max_size:
                assert len(max_size) == len(min_size), "max_size and min_size should have same length."
        if max_size:
            num_priors_per_location = (2 + len(aspect_ratio)) * len(min_size)
        else:
            num_priors_per_location = (1 + len(aspect_ratio)) * len(min_size)
        if flip:
            num_priors_per_location += len(aspect_ratio) * len(min_size)
        step = []
        if len(steps) > i:
            step = steps[i]

        # Create location prediction layer.
        name = "{}_mbox_loc{}".format(from_layer, loc_postfix)
        num_loc_output = num_priors_per_location * 4;
        if not share_location:
            num_loc_output *= num_classes
        ConvBNLayer(net, from_layer, name, use_bn=use_batchnorm, use_relu=False, lr_mult=lr_mult,
            num_output=num_loc_output, kernel_size=kernel_size, pad=pad, stride=1, **bn_param)
        permute_name = "{}_perm".format(name)
        net[permute_name] = L.Permute(net[name], order=[0, 2, 3, 1])
        flatten_name = "{}_flat".format(name)
        net[flatten_name] = L.Flatten(net[permute_name], axis=1)
        loc_layers.append(net[flatten_name])

        # Create confidence prediction layer.
        name = "{}_mbox_conf{}".format(from_layer, conf_postfix)
        num_conf_output = num_priors_per_location * num_classes;
        ConvBNLayer(net, from_layer, name, use_bn=use_batchnorm, use_relu=False, lr_mult=lr_mult,
            num_output=num_conf_output, kernel_size=kernel_size, pad=pad, stride=1, **bn_param)
        permute_name = "{}_perm".format(name)
        net[permute_name] = L.Permute(net[name], order=[0, 2, 3, 1])
        flatten_name = "{}_flat".format(name)
        net[flatten_name] = L.Flatten(net[permute_name], axis=1)
        conf_layers.append(net[flatten_name])

        # Create prior generation layer.
        name = "{}_mbox_priorbox".format(from_layer)
        net[name] = L.PriorBox(net[from_layer], net[data_layer], min_size=min_size,
                clip=clip, variance=prior_variance, offset=offset)
        if max_size:
            net.update(name, {'max_size': max_size})
        if aspect_ratio:
            net.update(name, {'aspect_ratio': aspect_ratio, 'flip': flip})
        if step:
            net.update(name, {'step': step})
        if img_height != 0 and img_width != 0:
            if img_height == img_width:
                net.update(name, {'img_size': img_height})
            else:
                net.update(name, {'img_h': img_height, 'img_w': img_width})
        priorbox_layers.append(net[name])

        # Create objectness prediction layer.
        if use_objectness:
            name = "{}_mbox_objectness".format(from_layer)
            num_obj_output = num_priors_per_location * 2;
            ConvBNLayer(net, from_layer, name, use_bn=use_batchnorm, use_relu=False, lr_mult=lr_mult,
                num_output=num_obj_output, kernel_size=kernel_size, pad=pad, stride=1, **bn_param)
            permute_name = "{}_perm".format(name)
            net[permute_name] = L.Permute(net[name], order=[0, 2, 3, 1])
            flatten_name = "{}_flat".format(name)
            net[flatten_name] = L.Flatten(net[permute_name], axis=1)
            objectness_layers.append(net[flatten_name])

    # Concatenate priorbox, loc, and conf layers.
    mbox_layers = []
    name = "mbox_loc"
    net[name] = L.Concat(*loc_layers, axis=1)
    mbox_layers.append(net[name])
    name = "mbox_conf"
    net[name] = L.Concat(*conf_layers, axis=1)
    mbox_layers.append(net[name])
    name = "mbox_priorbox"
    net[name] = L.Concat(*priorbox_layers, axis=2)
    mbox_layers.append(net[name])
    if use_objectness:
        name = "mbox_objectness"
        net[name] = L.Concat(*objectness_layers, axis=1)
        mbox_layers.append(net[name])

    return mbox_layers
