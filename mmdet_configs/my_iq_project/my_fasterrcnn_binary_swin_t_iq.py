
_base_ = [
    '../_base_/models/faster-rcnn_r50_fpn.py',
    '../_base_/datasets/coco_detection.py',
    '../_base_/schedules/schedule_1x.py',
    '../_base_/default_runtime.py'
]

# load_from = '/home/tppan/dataset/competition_v2/mmdetect_my/mmdetection/work_dirs/my_fasterrcnn_swin_t_iq/epoch_40.pth'
# -----------------------------------------------------------------
# 2. 数据集和元信息设定 (Dataset and Metainfo Settings)
# -----------------------------------------------------------------
# 你的数据集根目录
data_root = '/home/tppan/dataset/competition_v2/datasets/fixed_time_window_Twin_for_yolo_binary/'

# (### 必须修改 ###) 你的类别数量 (不包括背景)
num_classes = 1

# (### 必须修改 ###) 你的类别名称
metainfo = {
    'classes': ('class_0'),
    # 可选：为每个类别指定调色板，用于可视化
    'palette': [
        (220, 20, 60)
    ]
}

# COCO 格式标注文件
train_ann_file = 'labels/labels_clean/train2017/train_coco.json'
val_ann_file = 'labels/labels_clean/val2017/val_coco.json'

# 图像尺寸
image_size = (672, 672)

# MMDetection 3.x 推荐的数据集类型定义方式
dataset_type = 'CocoDataset'







pretrained = 'https://github.com/SwinTransformer/storage/releases/download/v1.0.0/swin_tiny_patch4_window7_224.pth'


# 模型配置
model = dict(
    # A. 骨干网络 Backbone: Swin-T (与你的配置保持一致)
    backbone=dict(
        _delete_=True,
        type='SwinTransformer',
        embed_dims=96,
        depths=[2, 2, 6, 2],
        num_heads=[3, 6, 12, 24],
        window_size=7,
        mlp_ratio=4,
        qkv_bias=True,
        qk_scale=None,
        drop_rate=0.,
        attn_drop_rate=0.,
        drop_path_rate=0.2,
        patch_norm=True,
        out_indices=(0, 1, 2, 3),
        with_cp=False,
        convert_weights=True,
        init_cfg=dict(type='Pretrained', checkpoint=pretrained)),

    # B. 颈部 Neck: PAFPN (与你的配置保持一致)
    neck=dict(
        type='PAFPN',
        in_channels=[96, 192, 384, 768],
        out_channels=256,
        num_outs=5),

    # C. RPN 部分 (与你的配置保持一致)
    rpn_head=dict(
        type='RPNHead',
        in_channels=256,
        feat_channels=256,
        anchor_generator=dict(
            type='AnchorGenerator',
            scales=[4],
            ratios=[0.1, 0.3, 1.0, 2.0, 4.0, 8.0],
            strides=[4, 8, 16, 32, 64]),
        bbox_coder=dict(
            type='DeltaXYWHBBoxCoder',
            target_means=[.0, .0, .0, .0],
            target_stds=[1.0, 1.0, 1.0, 1.0]),
        loss_cls=dict(
            type='CrossEntropyLoss', use_sigmoid=True, loss_weight=1.0),
        loss_bbox=dict(type='SmoothL1Loss', beta=1.0, loss_weight=1.0)),

    # D. RoI Head 部分 (核心修改)
    roi_head=dict(
        type='StandardRoIHead',  # <-- 2. RoI Head 类型改为 StandardRoIHead
        bbox_roi_extractor=dict(
            type='SingleRoIExtractor',
            roi_layer=dict(type='RoIAlign', output_size=7, sampling_ratio=0),
            out_channels=256,
            featmap_strides=[4, 8, 16, 32]),
        # bbox_head 从列表变为单个字典，选取了原配置的第一个 stage
        bbox_head=dict(
            type='ConvFCBBoxHead',
            num_shared_convs=2,
            num_shared_fcs=2,
            in_channels=256,
            conv_out_channels=256,
            fc_out_channels=1024,
            roi_feat_size=7,
            num_classes=num_classes,
            bbox_coder=dict(
                type='DeltaXYWHBBoxCoder',
                target_means=[0., 0., 0., 0.],
                target_stds=[0.1, 0.1, 0.2, 0.2]), # <-- 使用了原配置第一个 stage 的 stds
            reg_class_agnostic=False, # FasterRCNN 通常设为 False
            loss_cls=dict(
                type='CrossEntropyLoss', use_sigmoid=False, loss_weight=1.0),
            loss_bbox=dict(type='SmoothL1Loss', beta=1.0, loss_weight=1.0))
    ),

    # E. 训练和测试配置 (核心修改)
    train_cfg=dict(
        rpn=dict(
            assigner=dict(
                type='MaxIoUAssigner',
                pos_iou_thr=0.7,
                neg_iou_thr=0.3,
                min_pos_iou=0.3,
                match_low_quality=True,
                ignore_iof_thr=-1),
            sampler=dict(
                type='RandomSampler',
                num=256,
                pos_fraction=0.5,
                neg_pos_ub=-1,
                add_gt_as_proposals=False),
            allowed_border=-1,
            pos_weight=-1,
            debug=False),
        rpn_proposal=dict(
            nms_pre=2000,
            max_per_img=1000,
            nms=dict(type='nms', iou_threshold=0.7), # 在 RPN proposal 后也常用 0.7
            min_bbox_size=0),
        # rcnn 从列表变为单个字典，选取并调整了原配置的第一个 stage
        rcnn=dict( # <-- 3. rcnn 配置从列表变为字典
            assigner=dict(
                type='MaxIoUAssigner',
                pos_iou_thr=0.5,  # <-- FasterRCNN 标准 IoU 阈值
                neg_iou_thr=0.5,
                min_pos_iou=0.5,
                match_low_quality=False,
                ignore_iof_thr=-1),
            sampler=dict(
                type='RandomSampler',
                num=512,
                pos_fraction=0.25,
                neg_pos_ub=-1,
                add_gt_as_proposals=True),
            pos_weight=-1,
            debug=False)
    ),

    test_cfg=dict(
        rpn=dict(
            nms_pre=1000,
            max_per_img=1000,
            nms=dict(type='nms', iou_threshold=0.7),
            min_bbox_size=0),
        rcnn=dict(
            score_thr=0.01,
            nms=dict(type='nms', iou_threshold=0.3),
            max_per_img=100)
    )
)


train_pipeline = [
    dict(type='LoadImageFromFile', backend_args=None),
    dict(type='LoadAnnotations', with_bbox=True),
    dict(type='Resize', scale=image_size, keep_ratio=True),



    # dict(type='CachedMosaic', img_scale=image_size, pad_val=114.0),
    dict(
        type='RandomResize',
        scale=image_size,
        ratio_range=(0.1, 2.0),
        keep_ratio=True),
    dict(type='RandomCrop', crop_size=image_size),
    # dict(type='YOLOXHSVRandomAug'),
    dict(type='RandomFlip', prob=0.5),
    dict(type='Resize', scale=image_size, keep_ratio=True),
    dict(type='Pad', size=image_size, pad_val=dict(img=(114, 114, 114))),
    # dict(
    #     type='CachedMixUp',
    #     img_scale=image_size,
    #     ratio_range=(1.0, 1.0),
    #     max_cached_images=20,
    #     pad_val=(114, 114, 114)),

    dict(type='PackDetInputs')
]


# 测试数据流
test_pipeline = [
    dict(type='LoadImageFromFile', backend_args=None),
    dict(type='Resize', scale=image_size, keep_ratio=True),
    # 注意: 测试时也需要加载标注，因为评估器需要用它来计算 mAP
    dict(type='LoadAnnotations', with_bbox=True),
    dict(
        type='PackDetInputs',
        meta_keys=('img_id', 'img_path', 'ori_shape', 'img_shape',
                   'scale_factor', 'gt_bboxes', 'gt_bboxes_labels') # 评估需要 gt 信息
    )
]

# -----------------------------------------------------------------
# 5. 数据加载器和评估器 (Dataloaders and Evaluator)
# -----------------------------------------------------------------
train_batch_size = 16
num_workers = 4

train_dataloader = dict(
    batch_size=train_batch_size,
    num_workers=num_workers,
    persistent_workers=True,
    sampler=dict(type='DefaultSampler', shuffle=True),
    # batch_sampler=dict(type='AspectRatioBatchSampler'),
    dataset=dict(
        type=dataset_type,
        data_root=data_root,
        metainfo=metainfo,
        ann_file=train_ann_file,
        data_prefix=dict(img='images/train2017/'),
        filter_cfg=dict(filter_empty_gt=True, min_size=32),
        pipeline=train_pipeline,
        backend_args=None
    )
)

val_dataloader = dict(
    batch_size=1,
    num_workers=num_workers,
    persistent_workers=True,
    drop_last=False,
    sampler=dict(type='DefaultSampler', shuffle=False),
    dataset=dict(
        type=dataset_type,
        data_root=data_root,
        metainfo=metainfo,
        ann_file=val_ann_file,
        data_prefix=dict(img='images/val2017/'),
        test_mode=True,
        pipeline=test_pipeline,
        backend_args=None
    )
)

# 验证集评估器
val_evaluator = dict(
    type='CocoMetric',
    ann_file=data_root + val_ann_file,
    metric='bbox',
    format_only=False,
    backend_args=None
)

# 测试集直接复用验证集的配置
test_dataloader = val_dataloader
test_evaluator = val_evaluator

# -----------------------------------------------------------------
# 6. 训练策略 (Training Strategy)
# -----------------------------------------------------------------
# MMDetection 3.x 的训练循环配置
max_epochs = 100
train_cfg = dict(type='EpochBasedTrainLoop', max_epochs=max_epochs, val_interval=1)
val_cfg = dict(type='ValLoop')
test_cfg = dict(type='TestLoop')

# 优化器: Swin Transformer 推荐使用 AdamW
optim_wrapper = dict(
    type='OptimWrapper',
    optimizer=dict(
        _delete_=True,  # 删除 _base_ 中的 SGD
        type='AdamW',
        lr=0.0001,
        # lr=0.00005,
        betas=(0.9, 0.999),
        weight_decay=0.001),
    paramwise_cfg=dict(
        custom_keys={
            'absolute_pos_embed': dict(decay_mult=0.),
            'relative_position_bias_table': dict(decay_mult=0.),
            'norm': dict(decay_mult=0.)
        }))

# 学习率调度器
param_scheduler = [
    dict(
        type='LinearLR', start_factor=0.001, by_epoch=False, begin=0, end=500),
    dict(
        type='CosineAnnealingLR',
        T_max=max_epochs,
        by_epoch=True,
        begin=0,
        end=max_epochs,
    )
]