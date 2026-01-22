# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
"""Module providing a class to recognizer pdf layout."""
import math
from typing import List

import cv2
import numpy as np
from pdf2image import convert_from_path

from doc_process.processors.base.adapter.layout_recog_adapter import LayoutRecogAdapter
from doc_process.utils.check_utils import CheckUtils
from doc_process.utils.error_code import ProcessorException, ErrorCode
from doc_process.utils.file_utils import FileUtils

ZOOMIN = 2
LABELS = [
    "_background_", "Text", "Title", "Figure", "Figure caption", "Table", "Table caption", "Header", "Footer",
    "Reference", "Equation"
]
SCALE_FACTOR_KEY = "scale_factor"


def xywh2xyxy(x):
    """ convert coordinate """
    # [x, y, w, h] to [x1, y1, x2, y2]
    y = np.copy(x)
    y[:, 0] = x[:, 0] - x[:, 2] / 2
    y[:, 1] = x[:, 1] - x[:, 3] / 2
    y[:, 2] = x[:, 0] + x[:, 2] / 2
    y[:, 3] = x[:, 1] + x[:, 3] / 2
    return y


def compute_iou(box, boxes):
    """ compute box iou """
    # Compute xmin, ymin, xmax, ymax for both boxes
    xmin = np.maximum(box[0], boxes[:, 0])
    ymin = np.maximum(box[1], boxes[:, 1])
    xmax = np.minimum(box[2], boxes[:, 2])
    ymax = np.minimum(box[3], boxes[:, 3])

    # Compute intersection area
    intersection_area = np.maximum(0, xmax - xmin) * np.maximum(0, ymax - ymin)

    # Compute union area
    box_area = (box[2] - box[0]) * (box[3] - box[1])
    boxes_area = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    union_area = box_area + boxes_area - intersection_area

    # Compute IoU
    iou = intersection_area / union_area

    return iou


def iou_filter(boxes, scores, iou_threshold):
    """ filter by iou """
    sorted_indices = np.argsort(scores)[::-1]

    keep_boxes = []
    while sorted_indices.size > 0:
        # Pick the last box
        box_id = sorted_indices[0]
        keep_boxes.append(box_id)

        # Compute IoU of the picked box with the rest
        ious = compute_iou(boxes[box_id, :], boxes[sorted_indices[1:], :])

        # Remove boxes with IoU over the threshold
        keep_indices = np.where(ious < iou_threshold)[0]

        sorted_indices = sorted_indices[keep_indices + 1]

    return keep_boxes


class LayoutRecogAdapterImpl(LayoutRecogAdapter):
    """ Implementation of pdf Layout Recognizer Adapter"""

    def __init__(self, config, zoom_in=2, batch_size=16):
        CheckUtils.check_type(config, dict, "config")
        CheckUtils.check_type(config.get("parser", {}), dict, "parser")
        CheckUtils.check_type(config.get("parser", {}).get("pdf", {}), dict, "parser.pdf")
        CheckUtils.check_type(config.get("parser", {}).get("pdf", {}).get("layout_label", {}), dict,
                              "parser.pdf.layout_label")
        enable_mode = config.get("parser", {}).get("pdf", {}).get("layout_label", {}).get("enable_mode", "close")
        if enable_mode not in ["all", "sci_paper", "close"]:
            raise ProcessorException(ErrorCode.TYPE_ERROR, "enable_mode not in ['all', 'sci_paper', 'close'].")
        if enable_mode == "close":
            return
        # 当enable_mode！=close时，model_path必填
        model_path = config.get("parser", {}).get("pdf", {}).get("layout_label", {}).get("model_path", "")
        score_th = config.get("parser", {}).get("pdf", {}).get("layout_label", {}).get("model_score_th", 0.9)
        FileUtils.check_file(model_path)
        CheckUtils.check_type(score_th, float, "parser.pdf.layout_label.model_score_th")
        CheckUtils.check_range(score_th, min_open=0, max_open=1)
        import onnxruntime as ort
        self.ort_sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self.input_names = [node.name for node in self.ort_sess.get_inputs()]
        self.output_names = [node.name for node in self.ort_sess.get_outputs()]
        self.input_shape = self.ort_sess.get_inputs()[0].shape[2:4]
        self.label_list = LABELS
        self.zoom_in = zoom_in
        self.score_th = score_th
        self.batch_size = batch_size

    def forward(self, path: str = "") -> List[List[dict]]:
        """ 对输入的PDF文档，解析其版面，获取每一页的版面元素列表，表中元素为dict类型，包括"type", "bbox", "score"字段 """
        image_list = self.convert_pdf_2_images(path)
        res = []
        imgs = []
        for img in image_list:
            if not isinstance(img, np.ndarray):
                imgs.append(np.array(img))
            else:
                imgs.append(img)

        batch_loop_cnt = math.ceil(float(len(imgs)) / self.batch_size)
        for i in range(batch_loop_cnt):
            start_index = i * self.batch_size
            end_index = min((i + 1) * self.batch_size, len(imgs))
            batch_image_list = imgs[start_index:end_index]
            inputs = self.preprocess(batch_image_list)
            for ins in inputs:
                bb_list = self.postprocess(
                    self.ort_sess.run(None, {k: v for k, v in ins.items() if k in self.input_names})[0],
                    ins,
                    self.score_th
                )
                res.append(bb_list)
        return res

    def preprocess(self, image_list):
        """ preprocess input pdf page images """
        inputs = []
        hh, ww = self.input_shape
        for img in image_list:
            h, w = img.shape[:2]
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img = cv2.resize(np.array(img).astype("float32"), (ww, hh))
            # Scale input pixel values to 0 to 1
            img /= 255.0
            img = img.transpose(2, 0, 1)
            img = img[np.newaxis, :, :, :].astype(np.float32)
            inputs.append({self.input_names[0]: img, SCALE_FACTOR_KEY: [w / ww, h / hh]})
        return inputs

    def postprocess(self, boxes, inputs, th):
        """ postprocess output boxes """
        boxes = np.squeeze(boxes).T
        # Filter out object confidence scores below threshold
        scores = np.max(boxes[:, 4:], axis=1)
        boxes = boxes[scores > th, :]
        scores = scores[scores > th]
        if len(boxes) == 0:
            return []

        # Get the class with the highest confidence
        class_ids = np.argmax(boxes[:, 4:], axis=1)
        boxes = boxes[:, :4]
        input_shape = np.array([inputs[SCALE_FACTOR_KEY][0], inputs[SCALE_FACTOR_KEY][1], inputs[SCALE_FACTOR_KEY][0],
                                inputs[SCALE_FACTOR_KEY][1]])
        boxes = np.multiply(boxes, input_shape, dtype=np.float32)
        boxes = xywh2xyxy(boxes)

        unique_class_ids = np.unique(class_ids)
        indices = []
        for class_id in unique_class_ids:
            class_indices = np.where(class_ids == class_id)[0]
            class_boxes = boxes[class_indices, :]
            class_scores = scores[class_indices]
            class_keep_boxes = iou_filter(class_boxes, class_scores, 0.2)
            indices.extend(class_indices[class_keep_boxes])

        return [{
            "type": self.label_list[class_ids[i]].lower(),
            "bbox": [float(t) / self.zoom_in for t in boxes[i].tolist()],
            "score": float(scores[i])
        } for i in indices]

    def convert_pdf_2_images(self, path):
        """ convert pdf file to page images """
        imgs = convert_from_path(path, dpi=72 * self.zoom_in)  # pdf2image代替fitz进行转换，dpi设置为72，是为了对齐fitz输出
        return imgs
