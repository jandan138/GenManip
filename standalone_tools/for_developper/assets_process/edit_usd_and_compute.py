"""
We recommend using a independent conda environment to run this script.

conda create -n usd python=3.10
conda activate usd
pip install usd-core==24.11
pip install open3d numpy shapely
"""

import json
import numpy as np
import open3d as o3d
import os
from pxr import Usd, UsdGeom, Sdf  # type: ignore
from shapely.geometry import Polygon
from tqdm import tqdm


def move_prim(stage: Usd.Stage, old_path: str, new_path: str):
    old_path = Sdf.Path(old_path)
    new_path = Sdf.Path(new_path)
    old_prim = stage.GetPrimAtPath(old_path)
    if not old_prim or not old_prim.IsValid():
        print(f"[Error] Prim at {old_path} does not exist.")
        return
    if stage.GetPrimAtPath(new_path).IsValid():
        print(f"[Error] Prim at {new_path} already exists.")
        return
    layer = stage.GetEditTarget().GetLayer()
    if not Sdf.CopySpec(layer, old_path, layer, new_path):
        print(f"[Error] Failed to copy spec from {old_path} to {new_path}")
        return
    stage.RemovePrim(old_path)


def add_prim_from_asset(stage: Usd.Stage, prim_path: str, asset_path: str):
    prim_path = Sdf.Path(prim_path)
    if stage.GetPrimAtPath(prim_path).IsValid():
        print(f"[Error] Prim at {prim_path} already exists.")
        return
    prim = stage.DefinePrim(prim_path, "Xform")
    prim.GetReferences().AddReference(asset_path)


def save_stage_as(stage: Usd.Stage, new_path: str):
    new_layer = Sdf.Layer.CreateNew(new_path)
    if not new_layer:
        return
    stage.Export(new_path)


def delete_prim(stage: Usd.Stage, prim_path: str):
    prim_path = Sdf.Path(prim_path)
    prim = stage.GetPrimAtPath(prim_path)
    if prim and prim.IsValid():
        stage.RemovePrim(prim_path)


def print_prim_tree(prim, prefix="", is_last=True):
    RESET = "\033[0m"
    COLORS = {
        "Xform": "\033[94m",
        "Mesh": "\033[95m",
        "Camera": "\033[93m",
        "Light": "\033[96m",
        "Default": "\033[92m",
        "Type": "\033[91m",
    }
    connector = "└── " if is_last else "├── "
    prim_name = prim.GetName()
    prim_type = prim.GetTypeName()
    color = COLORS.get(prim_type, COLORS["Default"])
    color_type = COLORS["Type"]
    colored_name = f"{color}{prim_name}{RESET}"
    colored_type = f"{color_type} ({prim_type}){RESET}" if prim_type else ""
    print(prefix + connector + colored_name + colored_type)
    children = prim.GetChildren()
    count = len(children)
    for i, child in enumerate(children):
        is_last_child = i == count - 1
        extension = "    " if is_last else "│   "
        print_prim_tree(child, prefix + extension, is_last_child)


def recursive_parse(prim):
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
    if prim.IsA(UsdGeom.Mesh) and len(children) == 0:
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


def get_world_mesh_from_prim(prim):
    (
        points,
        faceuv,
        normals,
        faceVertexCounts,
        faceVertexIndices,
        mesh_list,
    ) = recursive_parse(prim)

    return (
        points,
        faceuv,
        normals,
        faceVertexCounts,
        faceVertexIndices,
        mesh_list,
    )


def get_mesh_from_points_and_faces(points, faceVertexCounts, faceVertexIndices):
    mesh = o3d.geometry.TriangleMesh()
    mesh.vertices = o3d.utility.Vector3dVector(points)
    triangles = []
    idx = 0
    for count in faceVertexCounts:
        if count == 3:
            triangles.append(faceVertexIndices[idx : idx + 3])
        idx += count
    mesh.triangles = o3d.utility.Vector3iVector(triangles)
    mesh.compute_vertex_normals()
    return mesh


def get_mesh_from_prim(prim):
    points, faceuv, normals, faceVertexCounts, faceVertexIndices, mesh_total = (
        recursive_parse(prim)
    )
    points += np.array(prim.GetAttribute("xformOp:transform").Get()[3][0:3])
    mesh = get_mesh_from_points_and_faces(points, faceVertexCounts, faceVertexIndices)
    return mesh


def get_pcd_from_mesh(mesh, num_points=1000):
    pcd = mesh.sample_points_uniformly(number_of_points=num_points)
    return pcd


def compute_pcd_bbox(pcd):
    aabb = pcd.get_axis_aligned_bounding_box()
    return aabb


def compute_mesh_bbox(mesh):
    pcd = get_pcd_from_mesh(mesh)
    return compute_pcd_bbox(pcd)


def get_prim_bbox(prim):
    mesh = get_mesh_from_prim(prim)
    return compute_mesh_bbox(mesh)


def bbox_to_polygon(x, y, w, h):
    points = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    return Polygon(points)


if __name__ == "__main__":
    stage = Usd.Stage.Open(
        os.path.join("/home/gaoning/grasp_vla_assets/scenes/test_mona_lisa/scene.usd")
    )

    print_prim_tree(stage.GetPseudoRoot())
