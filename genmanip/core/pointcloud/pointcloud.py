"""
Copyright (c) 2025 Ning Gao, Shanghai Artificial Intelligence Laboratory
All rights reserved.

Licensed under the MIT License.
"""

from copy import deepcopy
from filelock import SoftFileLock
import os
from pathlib import Path

import numpy as np
import open3d as o3d
from tqdm import tqdm

from omni.isaac.core.prims import XFormPrim  # type: ignore
from omni.isaac.core.utils.prims import get_prim_at_path, get_prim_parent, get_prim_path  # type: ignore

from genmanip.core.pointcloud.transform import (
    forward_transform_mesh,
    inverse_transform_mesh,
    transform_between_meshes,
    transform_between_point_clouds,
)
from genmanip.core.pointcloud.utils import MeshInfo, PointCloudInfo
from genmanip.core.usd_utils import get_mesh_from_prim
from genmanip.utils.pc_utils import get_pcd_from_mesh


def get_current_mesh(
    object: XFormPrim, mesh_dict: MeshInfo
) -> o3d.geometry.TriangleMesh:
    scale = np.array([1, 1, 1])
    trans, quat = object.get_world_pose()
    quat = quat[[1, 2, 3, 0]]
    return transform_between_meshes(
        mesh_dict.mesh,
        mesh_dict.scale,
        mesh_dict.quat,
        mesh_dict.trans,
        scale,
        quat,
        trans,
    )


def get_current_meshList(
    object_list: dict[str, XFormPrim], mesh_dict: dict[str, MeshInfo]
) -> dict[str, o3d.geometry.TriangleMesh]:
    updatedMeshList = {}
    for key in mesh_dict:
        mesh = get_current_mesh(object_list[key], mesh_dict[key])
        if mesh is not None:
            updatedMeshList[key] = mesh
    return updatedMeshList


def get_current_pcList_by_meshList(
    object_list: dict[str, XFormPrim], mesh_list: dict[str, o3d.geometry.TriangleMesh]
) -> dict[str, np.ndarray]:
    mesh_list = get_current_meshList(object_list, mesh_list)
    return meshlist_to_pclist(mesh_list)


def get_current_pointCloud(
    object: XFormPrim, point_dict: PointCloudInfo
) -> o3d.geometry.PointCloud:
    scale = np.array([1, 1, 1])
    trans, quat = object.get_world_pose()
    quat = quat[[1, 2, 3, 0]]
    return transform_between_point_clouds(
        point_dict.points,
        point_dict.scale,
        point_dict.quat,
        point_dict.trans,
        scale,
        quat,
        trans,
    )


def get_current_pointCloutList(
    object_list: dict[str, XFormPrim], point_dict: dict[str, PointCloudInfo]
) -> dict[str, o3d.geometry.PointCloud]:
    updatedPointCloudList = {}
    for key in point_dict:
        updatedPointCloudList[key] = get_current_pointCloud(
            object_list[key], point_dict[key]
        )
    return updatedPointCloudList


def get_mesh_info_by_load(object: XFormPrim, mesh_path: str) -> MeshInfo | None:
    lock = SoftFileLock(mesh_path + "_soft.lock", timeout=600.0)
    mesh = None
    try:
        with lock:
            if os.path.exists(mesh_path):
                try:
                    mesh = o3d.io.read_triangle_mesh(mesh_path)
                except:
                    os.remove(mesh_path)
            if not os.path.exists(mesh_path):
                if not os.path.exists(mesh_path):
                    Path(mesh_path).parent.mkdir(parents=True, exist_ok=True)
                    try:
                        mesh = get_mesh_from_prim(object.prim)
                    except:
                        return None
                    scale = object.get_local_scale()
                    trans, quat = object.get_local_pose()
                    quat = quat[[1, 2, 3, 0]]
                    mesh = inverse_transform_mesh(mesh, scale, quat, trans)
                    print(f"save mesh to {mesh_path}")
                    o3d.io.write_triangle_mesh(mesh_path, mesh)
    except:
        os.remove(mesh_path + "_soft.lock")
        try:
            with lock:
                if os.path.exists(mesh_path):
                    try:
                        mesh = o3d.io.read_triangle_mesh(mesh_path)
                    except:
                        os.remove(mesh_path)
                if not os.path.exists(mesh_path):
                    if not os.path.exists(mesh_path):
                        Path(mesh_path).parent.mkdir(parents=True, exist_ok=True)
                        try:
                            mesh = get_mesh_from_prim(object.prim)
                        except:
                            return None
                        scale = object.get_local_scale()
                        trans, quat = object.get_local_pose()
                        quat = quat[[1, 2, 3, 0]]
                        mesh = inverse_transform_mesh(mesh, scale, quat, trans)
                        print(f"save mesh to {mesh_path}")
                        o3d.io.write_triangle_mesh(mesh_path, mesh)
        except:
            raise Exception(
                f"Filelock timeout, try to delete the lock file by python standalone_tools/cleanup_lockfiles.py"
            )
    if mesh is None:
        raise Exception(f"Failed to load mesh from {mesh_path}")
    mesh_info = MeshInfo()
    mesh_info.mesh = get_world_mesh(mesh, object.prim_path)
    mesh_info.trans, mesh_info.quat = object.get_world_pose()
    mesh_info.quat = mesh_info.quat[[1, 2, 3, 0]]
    mesh_info.scale = np.array([1, 1, 1])
    return mesh_info


def get_mesh_info(object: XFormPrim) -> MeshInfo | None:
    try:
        mesh = get_mesh_from_prim(object.prim)
    except:
        return None
    scale = object.get_local_scale()
    trans, quat = object.get_local_pose()
    quat = quat[[1, 2, 3, 0]]
    mesh = inverse_transform_mesh(mesh, scale, quat, trans)
    mesh_info = MeshInfo()
    mesh_info.mesh = get_world_mesh(mesh, object.prim_path)
    mesh_info.trans, mesh_info.quat = object.get_world_pose()
    mesh_info.quat = mesh_info.quat[[1, 2, 3, 0]]
    mesh_info.scale = np.array([1, 1, 1])
    return mesh_info


def get_world_mesh(
    mesh: o3d.geometry.TriangleMesh, prim_path: str
) -> o3d.geometry.TriangleMesh:
    prim = get_prim_at_path(prim_path)
    mesh = deepcopy(mesh)
    while get_prim_path(prim) != "/":
        scale = np.array(prim.GetAttribute("xformOp:scale").Get())
        trans = np.array(prim.GetAttribute("xformOp:translate").Get())
        quat = prim.GetAttribute("xformOp:orient").Get()
        if quat is not None:
            r = quat.GetReal()
            i, j, k = quat.GetImaginary()
            quat = np.array([i, j, k, r])
        else:
            quat = np.array([0, 0, 0, 1])
        mesh = forward_transform_mesh(mesh, scale, quat, trans)
        prim = get_prim_parent(prim)
    return mesh


def meshDict2pointCloudDict(
    mesh_dict: dict[str, MeshInfo],
) -> dict[str, PointCloudInfo]:
    pointcloud_dict = {}
    for key in mesh_dict:
        pointCloud_info = mesh_info2pointCloud_info(mesh_dict[key])
        if pointCloud_info is not None:
            pointcloud_dict[key] = pointCloud_info
    return pointcloud_dict


def meshlist_to_pclist(
    meshlist: dict[str, o3d.geometry.TriangleMesh],
) -> dict[str, np.ndarray]:
    pointcloudlist = {}
    for key in meshlist:
        try:
            if key == "00000000000000000000000000000000":
                pointcloudlist[key] = np.asarray(
                    get_pcd_from_mesh(meshlist[key], num_points=100000).points
                )
            else:
                pointcloudlist[key] = np.asarray(
                    get_pcd_from_mesh(meshlist[key], num_points=10000).points
                )
        except:
            continue
    return pointcloudlist


def mesh_info2pointCloud_info(mesh_info: MeshInfo) -> PointCloudInfo | None:
    try:
        points = np.asarray(get_pcd_from_mesh(mesh_info.mesh).points)
        scale = mesh_info.scale
        trans = mesh_info.trans
        quat = mesh_info.quat
        return PointCloudInfo(
            points=points,
            scale=scale,
            trans=trans,
            quat=quat,
        )
    except:
        return None


def objectList2meshList(
    object_list: dict[str, XFormPrim], mesh_folder_path: str | None = None
) -> dict[str, MeshInfo]:
    mesh_dict = {}
    for key in tqdm(object_list):
        if key == "defaultGroundPlane":
            continue
        if mesh_folder_path is not None:
            mesh_info = get_mesh_info_by_load(
                object_list[key], os.path.join(mesh_folder_path, f"{key}.obj")
            )
        else:
            mesh_info = get_mesh_info(object_list[key])
        if mesh_info is not None:
            mesh_dict[key] = mesh_info
    return mesh_dict


def objectList2pointCloudList(
    object_list: dict[str, XFormPrim], visualize: bool = False
) -> dict[str, PointCloudInfo]:
    mesh_dict = objectList2meshList(object_list)
    point_dict = meshDict2pointCloudDict(mesh_dict)
    if visualize:
        all_points = []
        for key in point_dict:
            all_points.append(point_dict[key].points)
        all_points = np.vstack(all_points)
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(all_points)
        o3d.visualization.draw_geometries([pcd])  # type: ignore
    return point_dict
