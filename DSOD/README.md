# DSOD: Learning Deeply Supervised Object Detectors from Scratch

## Update (02/26/2019)
We observe that if we simply increase the batch size (bs) on each GPU from 4 (Titan X) to 12 (P40) for training BN layers, our DSOD300 can achieve much better performance without any other modifications (see comparisons below). We think if we have a better solution to tune BN layers' params, e.g., Sync BN [1] or Group Norm [2] when training detectors from scratch **with limited batch size**, the accuracy may be higher. This is also consistent with [3]. 

*We have also provided some preliminary results on exploring the factors of training two-stage detectors from scratch in our extended [paper](https://arxiv.org/abs/1809.09294) (v2) [4].*

New results on PASCAL VOC test set:

| Method | VOC 2007 test *mAP* | # parameters | Models 
|:-------|:-----:|:-------:|:-------:|
| DSOD300 (07+12) bs=4 on each GPU | 77.7 | 14.8M | [Download (59.2M)](https://drive.google.com/open?id=0B4cvsEOB5eUCaGU3MkRkOENRWWc) |
| DSOD300 (07+12) bs=12 on each GPU | 78.9 | 14.8M | [Download (59.2M)](https://drive.google.com/open?id=1_ur6TYiLPUGsHoZQM1yxAZ2AXgSe-Qxm)|

[1] Chao Peng, Tete Xiao, Zeming Li, Yuning Jiang, Xiangyu Zhang, Kai Jia, Gang Yu, and Jian Sun. "Megdet: A large mini-batch object detector." In Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition, pp. 6181-6189. 2018.

[2] Yuxin Wu, and Kaiming He. "Group normalization." In Proceedings of the European Conference on Computer Vision (ECCV), pp. 3-19. 2018.

[3] Kaiming He, Ross Girshick, and Piotr Dollár. "Rethinking imagenet pre-training." In Proceedings of the IEEE International Conference on Computer Vision, pp. 4918-4927. 2019.

[4] Zhiqiang Shen, Zhuang Liu, Jianguo Li, Yu-Gang Jiang, Yurong Chen, and Xiangyang Xue. "Object detection from scratch with deep supervision." IEEE transactions on pattern analysis and machine intelligence (2019).

-------------------------------------------------------------------------------------

This repository contains the code for the following paper 

[DSOD: Learning Deeply Supervised Object Detectors from Scratch](http://openaccess.thecvf.com/content_ICCV_2017/papers/Shen_DSOD_Learning_Deeply_ICCV_2017_paper.pdf) (ICCV 2017).

[Zhiqiang Shen](http://www.zhiqiangshen.com)\*, [Zhuang Liu](https://liuzhuang13.github.io/)\*, [Jianguo Li](https://sites.google.com/site/leeplus/), [Yu-Gang Jiang](http://www.yugangjiang.info/), [Yurong chen](https://scholar.google.com/citations?user=MKRyHXsAAAAJ&hl=en), [Xiangyang Xue](https://scholar.google.com/citations?user=DTbhX6oAAAAJ&hl=en). (\*Equal Contribution)

The code is based on the [SSD](https://github.com/weiliu89/caffe/tree/ssd) framework. 

Other Implementations:
[[Pytorch]](https://github.com/chenyuntc/dsod.pytorch) by Yun Chen, [[Pytorch]](https://github.com/uoip/SSD-variants) by uoip, [[Pytorch]](https://github.com/qqadssp/DSOD-Pytorch) by qqadssp, [[Pytorch]](https://github.com/Ellinier/DSOD-Pytorch-Implementation) by Ellinier , [[Mxnet]](https://github.com/leocvml/DSOD-gluon-mxnet) by Leo Cheng, [[Mxnet]](https://github.com/eureka7mt/mxnet-dsod) by eureka7mt, [[Tensorflow]](https://github.com/Windaway/DSOD-Tensorflow) by Windaway.


If you find this helps your research, please cite:

	@inproceedings{Shen2017DSOD,
		title = {DSOD: Learning Deeply Supervised Object Detectors from Scratch},
		author = {Shen, Zhiqiang and Liu, Zhuang and Li, Jianguo and Jiang, Yu-Gang and Chen, Yurong and Xue, Xiangyang},
		booktitle = {ICCV},
		year = {2017}
		}
		
     @article{shen2018object,
           title={Object Detection from Scratch with Deep Supervision},
           author={Shen, Zhiqiang and Liu, Zhuang and Li, Jianguo and Jiang, Yu-Gang and Chen, Yurong and Xue, Xiangyang},
           journal={arXiv preprint arXiv:1809.09294},
           year={2018}
        }

## Introduction

DSOD focuses on the problem of training object detector from scratch (without pretrained models on ImageNet). 
To the best of our knowledge, this is the first work that trains neural object detectors from scratch with state-of-the-art performance. 
In this work, we contribute a set of design principles for this purpose. One of the key findings is the deeply supervised structure enabled by [dense layer-wise connections](https://github.com/liuzhuang13/DenseNet), plays a critical role in learning a good detection model. Please see our paper for more details.

<div align=center>
<img src="https://user-images.githubusercontent.com/3794909/47570013-a6e9d000-d967-11e8-9e0d-cac62bc760a4.jpg" width="740">
</div>

<div align=center>
Figure 1: DSOD prediction layers with plain and dense structures (for 300×300 input).
</div> 

## Visualization

0. Visualizations of network structures (tools from [ethereon](http://ethereon.github.io/netscope/quickstart.html), ignore the warning messages):
	- [DSOD300] (http://ethereon.github.io/netscope/#/gist/b17d01f3131e2a60f9057b5d3eb9e04d)

## Results & Models

The tables below show the results on PASCAL VOC 2007, 2012 and MS COCO.

PASCAL VOC test results:

| Method | VOC 2007 test *mAP* | fps (Titan X) | # parameters | Models 
|:-------|:-----:|:-------:|:-------:|:-------:|
| DSOD300_smallest (07+12) | 73.6 | - | 5.9M | [Download (23.5M)](https://drive.google.com/open?id=0B4cvsEOB5eUCNXZ3eWNRNHZTdFk) |
| DSOD300_lite (07+12) | 76.7 | 25.8 | 10.4M | [Download (41.8M)](https://drive.google.com/open?id=0B4cvsEOB5eUCQVozLVhONS1EX2s) |
| DSOD300 (07+12) | 77.7 | 17.4 | 14.8M | [Download (59.2M)](https://drive.google.com/open?id=0B4cvsEOB5eUCaGU3MkRkOENRWWc) |
| DSOD300 (07+12+COCO) | 81.7 | 17.4 | 14.8M | [Download (59.2M)](https://drive.google.com/open?id=0B4cvsEOB5eUCa3lDWTNIa1BfMUU)|

| Method | VOC 2012 test *mAP* | fps | # parameters| Models 
|:-------|:-----:|:-----:|:-------:|:-------:|
| DSOD300 (07++12) | 76.3 | 17.4 | 14.8M | [Download (59.2M)](https://drive.google.com/open?id=0B4cvsEOB5eUCV2cyeU9qZVlhSEk) |
| DSOD300 (07++12+COCO) | 79.3 | 17.4 | 14.8M | [Download (59.2M)](https://drive.google.com/open?id=0B4cvsEOB5eUCLXhGdlUtT3B2cDQ) |

COCO test-dev 2015 result (COCO has more object categories than VOC dataset, so the model size is slightly bigger.):

| Method | COCO test-dev 2015 *mAP* (IoU 0.5:0.95) | Models
|:-------|:-----:|:-----:|
| DSOD300 (COCO trainval) | 29.3 | [Download (87.2M)](https://drive.google.com/open?id=0B4cvsEOB5eUCYXoxcGRCbVFMNms) |

## Preparation 

0. Install SSD (https://github.com/weiliu89/caffe/tree/ssd) following the instructions there, including: (1) Install SSD caffe; (2) Download PASCAL VOC 2007 and 2012 datasets; and (3) Create LMDB file. Make sure you can run it without any errors.

	Our PASCAL VOC LMDB files:
	
	| Method | LMDBs
	|:-------|:-----:|
	| Train on VOC07+12 and test on VOC07  | [Download](https://drive.google.com/open?id=1u6ngM9hEZabT2HyvzPdWpGgVTofD6jQ3) |
	| Train on VOC07++12 and test on VOC12 (Comp4)  | [Download](https://drive.google.com/open?id=1J2epI4zDFptw1RdpHAl0Z_Sphs14OtIE) |
	| Train on VOC12 and test on VOC12 (Comp3)  | [Download](https://drive.google.com/open?id=1r5DI3tVGXPYyKGAmBawKGkgROJQyh5i-) |

1. Create a subfolder `dsod` under `example/`, add files `DSOD300_pascal.py`, `DSOD300_pascal++.py`, `DSOD300_coco.py`, `score_DSOD300_pascal.py` and `DSOD300_detection_demo.py` to the folder `example/dsod/`.
2. Create a subfolder `grp_dsod` under `example/`, add files `GRP_DSOD320_pascal.py` and `score_GRP_DSOD320_pascal.py` to the folder `example/grp_dsod/`.
3. Replace the file `model_libs.py` in the folder `python/caffe/` with ours.

## Training & Testing

- Train a DSOD model on VOC 07+12:

  ```shell
  python examples/dsod/DSOD300_pascal.py
  ```

- Train a DSOD model on VOC 07++12:

  ```shell
  python examples/dsod/DSOD300_pascal++.py
  ```
  
- Train a DSOD model on COCO trainval:

  ```shell
  python examples/dsod/DSOD300_coco.py
  ```
  
- Evaluate the model (DSOD):

  ```shell
  python examples/dsod/score_DSOD300_pascal.py
  ```
  
- Run a demo (DSOD):

  ```shell
  python examples/dsod/DSOD300_detection_demo.py
  ```
  
- Train a GRP_DSOD model on VOC 07+12:

  ```shell
  python examples/grp_dsod/GRP_DSOD320_pascal.py
  ```
  
- Evaluate the model (GRP_DSOD):

  ```shell
  python examples/dsod/score_GRP_DSOD320_pascal.py
  ```
  
 **Note**: You can modify the file `model_lib.py` to design your own network structure as you like.

## Examples

<div align=center>
<img src="https://cloud.githubusercontent.com/assets/3794909/25331405/92d88c36-2915-11e7-93f3-3eb43963f5ac.jpg" width="780">
</div>

## Contact

Zhiqiang Shen (zhiqiangshen0214 at gmail.com) 

Zhuang Liu (liuzhuangthu at gmail.com)

Any comments or suggestions are welcome!
