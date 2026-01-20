# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
"""Module providing functions for Node."""


def group_nodes_by_pageid(nodes):
    """ group nodes to pages """
    if not nodes:
        return []
    page_nodes = [[nodes[0]]]
    for node in nodes[1:]:
        if node.page_id == page_nodes[-1][-1].page_id:
            page_nodes[-1].append(node)
        else:
            page_nodes.append([node])
    return page_nodes


def get_loc_intersection(loc1, loc2):
    """ get box intersection """
    x_inter1 = max(loc1[0], loc2[0])
    y_inter1 = max(loc1[1], loc2[1])
    x_inter2 = min(loc1[2], loc2[2])
    y_inter2 = min(loc1[3], loc2[3])

    inter_area = max(0, x_inter2 - x_inter1) * max(0, y_inter2 - y_inter1)

    area1 = (loc1[2] - loc1[0]) * (loc1[3] - loc1[1])
    area2 = (loc2[2] - loc2[0]) * (loc2[3] - loc2[1])

    return inter_area, area1, area2
