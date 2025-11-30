from isaacsim import SimulationApp  # type: ignore[import-untyped]

simulation_app = SimulationApp({"headless": True})  # False

from functools import partial
from pathlib import Path
from pxr import Sdf, Gf, Usd, UsdGeom, UsdUI  # type: ignore
from typing import List
import os
from omni.isaac.core.prims import XFormPrim  # type: ignore
import omni.usd  # type: ignore
import numpy as np
import open3d as o3d
import coacd
import trimesh


def __set_xform_prim_transform(prim: UsdGeom.Xformable, transform: Gf.Matrix4d):
    prim = UsdGeom.Xformable(prim)
    _, _, scale, rot_mat, translation, _ = transform.Factor()
    angles = rot_mat.ExtractRotation().Decompose(
        Gf.Vec3d.ZAxis(), Gf.Vec3d.YAxis(), Gf.Vec3d.XAxis()
    )
    rotation = Gf.Vec3f(angles[2], angles[1], angles[0])

    for xform_op in prim.GetOrderedXformOps():
        attr = xform_op.GetAttr()
        prim.GetPrim().RemoveProperty(attr.GetName())
    prim.ClearXformOpOrder()

    UsdGeom.XformCommonAPI(prim).SetTranslate(translation)
    UsdGeom.XformCommonAPI(prim).SetRotate(rotation)
    UsdGeom.XformCommonAPI(prim).SetScale(Gf.Vec3f(scale[0], scale[1], scale[2]))


def export(path: str, prims: List[Usd.Prim]):
    """Export prim to external USD file"""
    filename = Path(path).stem

    # TODO: stage.Flatten() is extreamly slow
    stage = omni.usd.get_context().get_stage()
    source_layer = stage.Flatten()
    target_layer = Sdf.Layer.CreateNew(path)
    target_stage = Usd.Stage.Open(target_layer)
    axis = UsdGeom.GetStageUpAxis(stage)
    UsdGeom.SetStageUpAxis(target_stage, axis)

    # All prims will be put under /Root
    if len(prims) > 1:
        root_path = Sdf.Path.absoluteRootPath.AppendChild("Root")
        UsdGeom.Xform.Define(target_stage, root_path)
    else:
        root_path = Sdf.Path.absoluteRootPath

    keep_transforms = len(prims) > 1

    center_point = Gf.Vec3d(0.0)
    transforms = []
    if keep_transforms:
        bound_box = Gf.BBox3d()
        bbox_cache = UsdGeom.BBoxCache(
            Usd.TimeCode.Default(), includedPurposes=[UsdGeom.Tokens.default_]
        )
        for prim in prims:
            xformable = UsdGeom.Xformable(prim)
            if xformable:
                local_bound_box = bbox_cache.ComputeWorldBound(prim)
                transforms.append(
                    xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
                )
                bound_box = Gf.BBox3d.Combine(bound_box, local_bound_box)
            else:
                transforms.append(None)

        center_point = bound_box.ComputeCentroid()
    else:
        transforms.append(Gf.Matrix4d(1.0))

    for i in range(len(transforms)):
        if transforms[i]:
            transforms[i] = transforms[i].SetTranslateOnly(
                transforms[i].ExtractTranslation() - center_point
            )

    # Set default prim name
    if len(prims) > 1:
        target_layer.defaultPrim = root_path.name
        # target_layer.SetDefaultPrim(prims[0].GetPath().name)

        for i in range(len(prims)):
            source_path = prims[i].GetPath()
            if len(prims) > 1 and transforms[i]:
                target_xform_path = root_path.AppendChild(source_path.name)
                target_xform_path = Sdf.Path(
                    omni.usd.get_stage_next_free_path(
                        target_stage, target_xform_path, False
                    )
                )
                target_xform = UsdGeom.Xform.Define(target_stage, target_xform_path)
                __set_xform_prim_transform(target_xform, transforms[i])
                target_path = target_xform_path.AppendChild(source_path.name)
            else:
                target_path = root_path.AppendChild(source_path.name)
                target_path = Sdf.Path(
                    omni.usd.get_stage_next_free_path(target_stage, target_path, False)
                )

            all_external_references = set([])

            def on_prim_spec_path(root_path, prim_spec_path):
                if prim_spec_path.IsPropertyPath():
                    return

                if prim_spec_path == Sdf.Path.absoluteRootPath:
                    return

                prim_spec = source_layer.GetPrimAtPath(prim_spec_path)
                if not prim_spec or not prim_spec.HasInfo(Sdf.PrimSpec.ReferencesKey):
                    return

                op = prim_spec.GetInfo(Sdf.PrimSpec.ReferencesKey)
                items = []
                items = op.ApplyOperations(items)

                for item in items:
                    if not item.primPath.HasPrefix(root_path):
                        all_external_references.add(item.primPath)

            # Traverse the source prim tree to find all references that are outside of the source tree.
            source_layer.Traverse(source_path, partial(on_prim_spec_path, source_path))

            # Copy dependencies
            for path in all_external_references:
                Sdf.CreatePrimInLayer(target_layer, path)
                Sdf.CopySpec(source_layer, path, target_layer, path)

            Sdf.CreatePrimInLayer(target_layer, target_path)
            Sdf.CopySpec(source_layer, source_path, target_layer, target_path)

            prim = target_stage.GetPrimAtPath(target_path)
            if transforms[i]:
                __set_xform_prim_transform(prim, Gf.Matrix4d(1.0))

            # Edit UI info of compound
            spec = target_layer.GetPrimAtPath(target_path)
            attributes = spec.attributes

            if UsdUI.Tokens.uiDisplayGroup not in attributes:
                attr = Sdf.AttributeSpec(
                    spec, UsdUI.Tokens.uiDisplayGroup, Sdf.ValueTypeNames.Token
                )
                attr.default = "Material Graphs"

            if UsdUI.Tokens.uiDisplayName not in attributes:
                attr = Sdf.AttributeSpec(
                    spec, UsdUI.Tokens.uiDisplayName, Sdf.ValueTypeNames.Token
                )
                attr.default = target_path.name

            if "ui:order" not in attributes:
                attr = Sdf.AttributeSpec(spec, "ui:order", Sdf.ValueTypeNames.Int)
                attr.default = 1024
    else:
        source_path = prims[0].GetPath()

        target_path = root_path.AppendChild(source_path.name)

        target_path = Sdf.Path(
            omni.usd.get_stage_next_free_path(target_stage, target_path, False)
        )
        target_layer.defaultPrim = source_path.name

        # all_external_references = set([])

        # def on_prim_spec_path(root_path, prim_spec_path):
        #     if prim_spec_path.IsPropertyPath():
        #         return

        #     if prim_spec_path == Sdf.Path.absoluteRootPath:
        #         return

        #     prim_spec = source_layer.GetPrimAtPath(prim_spec_path)
        #     if not prim_spec or not prim_spec.HasInfo(Sdf.PrimSpec.ReferencesKey):
        #         return

        #     op = prim_spec.GetInfo(Sdf.PrimSpec.ReferencesKey)
        #     items = []
        #     items = op.ApplyOperations(items)

        #     for item in items:
        #         if not item.primPath.HasPrefix(root_path):
        #             all_external_references.add(item.primPath)

        # # Traverse the source prim tree to find all references that are outside of the source tree.
        # source_layer.Traverse(source_path, partial(on_prim_spec_path, source_path))

        # Copy dependencies
        # for path in all_external_references:
        #     Sdf.CreatePrimInLayer(target_layer, path)
        #     Sdf.CopySpec(source_layer, path, target_layer, path)

        Sdf.CreatePrimInLayer(target_layer, target_path)
        Sdf.CopySpec(source_layer, source_path, target_layer, target_path)

        prim = target_stage.GetPrimAtPath(target_path)

        # Edit UI info of compound
        spec = target_layer.GetPrimAtPath(target_path)
        attributes = spec.attributes

        if UsdUI.Tokens.uiDisplayGroup not in attributes:
            attr = Sdf.AttributeSpec(
                spec, UsdUI.Tokens.uiDisplayGroup, Sdf.ValueTypeNames.Token
            )
            attr.default = "Material Graphs"

        if UsdUI.Tokens.uiDisplayName not in attributes:
            attr = Sdf.AttributeSpec(
                spec, UsdUI.Tokens.uiDisplayName, Sdf.ValueTypeNames.Token
            )
            attr.default = target_path.name

        if "ui:order" not in attributes:
            attr = Sdf.AttributeSpec(spec, "ui:order", Sdf.ValueTypeNames.Int)
            attr.default = 1024

    # Save
    target_layer.Save()


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


def get_mesh_from_points_and_faces(points, faceVertexCounts, faceVertexIndices):
    mesh = o3d.geometry.TriangleMesh()
    mesh.vertices = o3d.utility.Vector3dVector(points)
    triangles = []
    idx = 0
    for count in faceVertexCounts:
        if count == 3:
            triangles.append(faceVertexIndices[idx : idx + 3])
        elif count == 4:
            face_indices = faceVertexIndices[idx : idx + 4]
            triangles.append([face_indices[0], face_indices[1], face_indices[2]])
            triangles.append([face_indices[0], face_indices[2], face_indices[3]])
        elif count > 4:
            face_indices = faceVertexIndices[idx : idx + count]
            for i in range(1, count - 1):
                triangles.append(
                    [face_indices[0], face_indices[i], face_indices[i + 1]]
                )
        else:
            print(f"Warning: Skipping face with {count} vertices")
        idx += count
    mesh.triangles = o3d.utility.Vector3iVector(triangles)
    mesh.compute_vertex_normals()
    return mesh


def get_mesh_from_prim(prim):
    points, faceuv, normals, faceVertexCounts, faceVertexIndices, mesh_total = (
        recursive_parse(prim)
    )
    # points += np.array(prim.GetAttribute("xformOp:transform").Get()[3][0:3])
    mesh = get_mesh_from_points_and_faces(points, faceVertexCounts, faceVertexIndices)
    return mesh


def save_convex_hulls_as_obj(convex_hulls, output_path):
    with open(output_path, "w") as f:
        vertex_offset = 1
        for i, (vertices, faces) in enumerate(convex_hulls):
            f.write(f"o convex_part_{i}\n")
            for v in vertices:
                f.write(f"v {v[0]} {v[1]} {v[2]}\n")
            for face in faces:
                f.write(
                    f"f {face[0] + vertex_offset} {face[1] + vertex_offset} {face[2] + vertex_offset}\n"
                )
            vertex_offset += len(vertices)


def run_coacd(mesh_path, output_path):
    mesh = trimesh.load(mesh_path, force="mesh")
    mesh = coacd.Mesh(mesh.vertices, mesh.faces)  # type: ignore[attr-defined]
    parts = coacd.run_coacd(mesh)
    save_convex_hulls_as_obj(parts, output_path)
    return parts


def process_single_prim(prim: Usd.Prim, output_path: str, uuid: str):
    if os.path.exists(os.path.join(output_path, uuid + ".usd")) and os.path.exists(
        os.path.join(output_path, uuid + "_coacd.obj")
    ):
        return
    print(f"Processing {prim.GetPath()}")
    xform = XFormPrim(str(prim.GetPath()), name=prim.GetName())
    xform.set_world_pose([0, 0, 0], [1, 0, 0, 0])
    xform.set_local_scale([1, 1, 1])
    export(os.path.join(output_path, uuid + ".usd"), [prim])
    print(f"Exported {prim.GetName()} to {os.path.join(output_path, uuid + '.usd')}")
    mesh = get_mesh_from_prim(prim)
    if len(mesh.vertices) > 0:
        vertices_np = np.asarray(mesh.vertices)
        bbox_min = np.min(vertices_np, axis=0)
        bbox_max = np.max(vertices_np, axis=0)
        print(f"Mesh bounding box: min={bbox_min}, max={bbox_max}")
    success = o3d.io.write_triangle_mesh(os.path.join(output_path, uuid + ".obj"), mesh)
    if success:
        acd_mesh_path = os.path.join(output_path, uuid + "_coacd.obj")
        try:
            run_coacd(os.path.join(output_path, uuid + ".obj"), acd_mesh_path)
            print(f"Exported {prim.GetName()} to {acd_mesh_path}")
            os.remove(os.path.join(output_path, uuid + ".obj"))
            print(
                f"Deleted {prim.GetName()} from {os.path.join(output_path, uuid + '.obj')}"
            )
        except Exception as e:
            print(f"Error running coacd for {prim.GetName()}: {e}")
    else:
        print(
            f"Failed to export {prim.GetName()} to {os.path.join(output_path, uuid + '.obj')}"
        )
        print("Skipping coacd decomposition due to failed obj export")


def load_world_xform_prim(scene_path, scene_prim_path="/World"):
    scene_path = os.path.abspath(scene_path)
    omni.usd.get_context().new_stage()
    omni.usd.get_context().open_stage(scene_path)
    stage = omni.usd.get_context().get_stage()
    root = stage.GetPseudoRoot().GetAllChildren()[0]
    scene_xform = XFormPrim(
        str(root.GetPath()),
        name="World",
    )
    uuid = str(scene_xform.prim.GetAllChildren()[0].GetPath()).split("/")[-1]
    return scene_xform, uuid


def export_usds_from_usds(scene_path: str, output_path: str):
    from omni.isaac.core import World  # type: ignore

    os.makedirs(output_path, exist_ok=True)
    for path in os.listdir(scene_path):
        if path.endswith(".usd"):
            scene_xform, uuid = load_world_xform_prim(os.path.join(scene_path, path))
            world = World()
            world.reset()
            root = scene_xform.prim
            process_single_prim(root, output_path, path.split(".")[0])


if __name__ == "__main__":
    export_usds_from_usds(
        "saved/assets/scene_usds/IROS_scenes_collected/scene_cup/cups",
        "scene_usds/scene_cup/cups/",
    )
    export_usds_from_usds(
        "saved/assets/scene_usds/IROS_scenes_collected/scene_cup/plates",
        "scene_usds/scene_cup/plates/",
    )
    # export_usds_from_usds(
    #     "saved/assets/scene_usds/IROS_scenes_collected/scene_drink/bottles",
    #     "scene_usds/scene_drink/bottles/",
    # )
    simulation_app.close()
