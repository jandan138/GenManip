"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

import numpy as np
import open3d as o3d

from pxr import UsdGeom, Usd  # type: ignore

from genmanip.utils.standalone.pc_utils import (
    compute_mesh_bbox,
    compute_mesh_center,
    get_mesh_from_points_and_faces,
    get_pcd_from_mesh,
)


def recursive_parse(prim: Usd.Prim) -> tuple[list, list, list, list, list, list]:
    translation = prim.GetAttribute("xformOp:translate").Get()
    if translation is None:
        translation = np.zeros(3)
    else:
        translation = np.array(translation)
    scale = prim.GetAttribute("xformOp:scale").Get()
    if scale is None:
        scale = np.ones(3)
    else:
        scale = np.array(scale)
    orient = prim.GetAttribute("xformOp:orient").Get()
    if orient is None:
        orient = np.zeros([4, 1])
        orient[0] = 1.0
    else:
        r = orient.GetReal()
        i, j, k = orient.GetImaginary()
        orient = np.array([r, i, j, k]).reshape(4, 1)
    rotation_matrix = o3d.geometry.get_rotation_matrix_from_quaternion(orient)
    points_total = []
    faceuv_total = []
    normals_total = []
    faceVertexCounts_total = []
    faceVertexIndices_total = []
    mesh_total = []
    if prim.IsA(UsdGeom.Mesh):
        mesh_path = str(prim.GetPath()).split("/")[-1]
        if not mesh_path == "SM_Dummy":
            mesh_total.append(mesh_path)
            points = prim.GetAttribute("points").Get()
            normals = prim.GetAttribute("normals").Get()
            faceVertexCounts = prim.GetAttribute("faceVertexCounts").Get()
            faceVertexIndices = prim.GetAttribute("faceVertexIndices").Get()
            faceuv = prim.GetAttribute("primvars:st").Get()
            if points is None:
                points = []
            if normals is None:
                normals = []
            if faceVertexCounts is None:
                faceVertexCounts = []
            if faceVertexIndices is None:
                faceVertexIndices = []
            if faceuv is None:
                faceuv = []
            normals = [_ for _ in normals]
            faceVertexCounts = [_ for _ in faceVertexCounts]
            faceVertexIndices = [_ for _ in faceVertexIndices]
            faceuv = [_ for _ in faceuv]
            ps = []
            for p in points:
                x, y, z = p
                p = np.array((x, y, z))
                ps.append(p)
            points = ps
            base_num = len(points_total)
            for idx in faceVertexIndices:
                faceVertexIndices_total.append(base_num + idx)
            faceVertexCounts_total += faceVertexCounts
            faceuv_total += faceuv
            normals_total += normals
            points_total += points
    else:
        children = prim.GetChildren()
        for child in children:
            points, faceuv, normals, faceVertexCounts, faceVertexIndices, mesh_list = (
                recursive_parse(child)
            )
            base_num = len(points_total)
            for idx in faceVertexIndices:
                faceVertexIndices_total.append(base_num + idx)
            faceVertexCounts_total += faceVertexCounts
            faceuv_total += faceuv
            normals_total += normals
            points_total += points
            mesh_total += mesh_list
    new_points = []
    for i, p in enumerate(points_total):
        pn = np.array(p)
        pn *= scale
        pn = np.matmul(rotation_matrix, pn)
        pn += translation
        new_points.append(pn)
    return (
        new_points,
        faceuv_total,
        normals_total,
        faceVertexCounts_total,
        faceVertexIndices_total,
        mesh_total,
    )


def get_mesh_from_prim(prim: Usd.Prim) -> o3d.geometry.TriangleMesh:
    points, faceuv, normals, faceVertexCounts, faceVertexIndices, mesh_total = (
        recursive_parse(prim)
    )
    mesh = get_mesh_from_points_and_faces(points, faceVertexCounts, faceVertexIndices)
    return mesh


def get_prim_bbox(prim: Usd.Prim) -> o3d.geometry.AxisAlignedBoundingBox:
    mesh = get_mesh_from_prim(prim)
    return compute_mesh_bbox(mesh)


def get_prim_center(prim: Usd.Prim) -> np.ndarray:
    mesh = get_mesh_from_prim(prim)
    return compute_mesh_center(mesh)


def sample_points_from_prim(prim: Usd.Prim, num_points: int = 1000) -> np.ndarray:
    mesh = get_mesh_from_prim(prim)
    pcd = get_pcd_from_mesh(mesh, num_points)
    return np.asarray(pcd.points)
