"""Testes de integração com Blender real e arquivos produzidos em diretório temporário."""

import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import bpy

TEST_DIR = Path(__file__).resolve().parent
sys.path[:0] = [str(TEST_DIR), str(TEST_DIR.parents[1])]

import arvertes_studio
from arvertes_studio.blender import analysis, assets, ui
from arvertes_studio.core.reports import write_report
from fixture_glb import encode_glb, write_fixture


class BlenderIntegrationTests(unittest.TestCase):
    def setUp(self):
        scratch = self.enterContext(tempfile.TemporaryDirectory())
        self.directory = Path(scratch)
        self.previous_scene_name = bpy.context.scene.name
        test_scene = bpy.data.scenes.new("Integração Arvertes")
        self.test_scene_name = test_scene.name
        bpy.context.window.scene = test_scene
        self.addCleanup(self.restore_scene)

    def restore_scene(self):
        bpy.context.window.scene = bpy.data.scenes[self.previous_scene_name]
        test_scene = bpy.data.scenes.get(self.test_scene_name)
        if test_scene is not None:
            bpy.data.scenes.remove(test_scene)

    def import_fixture(self, mesh_count=4):
        path = self.directory / "Personagem sintético.glb"
        write_fixture(path, mesh_count)
        collection = assets.import_asset(bpy.context, str(path))
        return path, collection

    def category_collection(self, asset, mesh):
        matches = [child for child in asset.children_recursive if child.objects.get(mesh.name)]
        self.assertEqual(len(matches), 1)
        return matches[0]

    def test_fixture_with_58_meshes_and_report_export(self):
        path = self.directory / "Personagem sintético.glb"
        write_fixture(path)
        original_bytes = path.read_bytes()
        asset = assets.import_asset(bpy.context, str(path))
        report = analysis.analyze_asset(bpy.context, asset)
        summary = report["summary"]

        self.assertEqual(path.read_bytes(), original_bytes)
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["asset"], assets.asset_identity(asset))
        self.assertEqual(report["asset"]["source_file"], path.name)
        self.assertEqual(summary["object_count"], 58)
        self.assertEqual(summary["mesh_count"], 58)
        self.assertEqual(len(report["meshes"]), 58)
        self.assertEqual(len({mesh["data_name"] for mesh in report["meshes"]}), 58)
        self.assertEqual(summary["geometry_original"]["vertices"], 58 * 8)
        self.assertEqual(summary["geometry_original"]["edges"], 58 * 18)
        self.assertEqual(summary["geometry_original"]["faces"], 58 * 12)
        self.assertEqual(summary["geometry_original"]["triangles"], 58 * 12)
        self.assertIsNone(summary["geometry_evaluated"])
        self.assertEqual(summary["materials"], [])
        self.assertEqual(summary["meshes_without_materials"], 58)
        self.assertEqual(summary["meshes_without_uv"], 58)
        self.assertEqual(summary["armatures"], [])
        self.assertFalse(summary["has_armature"])
        self.assertFalse(summary["has_modifiers"])
        self.assertEqual({mesh["category"] for mesh in report["meshes"]}, {"unidentified"})
        issue_counts = Counter(issue["code"] for issue in report["issues"])
        self.assertEqual(issue_counts["no_uv"], 58)
        self.assertEqual(issue_counts["no_materials"], 58)

        target = self.directory / "Inventário sintético.json"
        write_report(report, target)
        payload = target.read_text(encoding="utf-8")
        self.assertEqual(json.loads(payload), report)
        self.assertIn("Personagem sintético.glb", payload)
        self.assertNotIn(str(self.directory), payload)

    def test_import_preserves_external_metadata_without_accepting_categories(self):
        path = self.directory / "Peça com metadados.glb"
        write_fixture(path, mesh_count=1, node_extras={
            "arvertes_category": "hair",
            "nota_da_peca": "Origem sintética",
        })
        asset = assets.import_asset(bpy.context, str(path))
        (mesh,) = assets.asset_objects(asset)

        self.assertEqual(assets.category_for(mesh), "unidentified")
        self.assertNotIn("arvertes_category", mesh)
        self.assertEqual(mesh["nota_da_peca"], "Origem sintética")

    def test_repeated_imports_and_invalid_files_preserve_scene(self):
        path, first = self.import_fixture()
        second = assets.import_asset(bpy.context, str(path))
        self.assertCountEqual(assets.list_assets(bpy.context.scene), [first, second])
        self.assertNotEqual(assets.asset_identity(first)["id"], assets.asset_identity(second)["id"])
        first_objects = set(assets.asset_objects(first))
        second_objects = set(assets.asset_objects(second))
        self.assertEqual(len(first_objects), 4)
        self.assertEqual(len(second_objects), 4)
        self.assertFalse(first_objects & second_objects)

        mesh = min(first_objects, key=lambda obj: obj.name)
        assets.select_mesh(bpy.context, mesh)
        bad_header = self.directory / "Truncado.glb"
        bad_header.write_bytes(b"glTF")
        invalid_document = self.directory / "Referência inválida.glb"
        invalid_document.write_bytes(encode_glb({
            "asset": {"version": "2.0"},
            "scene": 0,
            "scenes": [{"nodes": [0]}],
            "nodes": [{"mesh": 7}],
            "meshes": [],
        }))
        wrong_extension = path.with_suffix(".obj")
        wrong_extension.write_bytes(path.read_bytes())
        before_objects = set(bpy.data.objects)
        before_meshes = set(bpy.data.meshes)
        before_collections = set(bpy.data.collections)

        for invalid in (bad_header, wrong_extension, path.with_name("Ausente.glb"), invalid_document):
            with self.subTest(filepath=invalid.name):
                with self.assertRaises((ValueError, OSError, RuntimeError)):
                    assets.import_asset(bpy.context, str(invalid))
                self.assertCountEqual(assets.list_assets(bpy.context.scene), [first, second])
                self.assertEqual(set(bpy.data.objects), before_objects)
                self.assertEqual(set(bpy.data.meshes), before_meshes)
                self.assertEqual(set(bpy.data.collections), before_collections)
                self.assertEqual(bpy.context.selected_objects, [mesh])
                self.assertEqual(bpy.context.view_layer.objects.active, mesh)

    def test_failed_import_rolls_back_partial_native_data_and_selection(self):
        path, asset = self.import_fixture(mesh_count=1)
        (existing,) = assets.asset_objects(asset)
        assets.select_mesh(bpy.context, existing)
        view_layer = bpy.context.view_layer
        view_layer.active_layer_collection = view_layer.layer_collection.children[asset.name]
        active_layer = view_layer.active_layer_collection
        original_ids = {item.as_pointer() for item in bpy.data.all_ids}

        def fail_after_creating_data(_filepath):
            collection = bpy.data.collections.new("Coleção parcial")
            bpy.context.scene.collection.children.link(collection)
            data = bpy.data.meshes.new("Dados parciais")
            data.materials.append(bpy.data.materials.new("Material parcial"))
            partial = bpy.data.objects.new("Objeto parcial", data)
            collection.objects.link(partial)
            view_layer.update()
            existing.select_set(False)
            partial.select_set(True)
            view_layer.objects.active = partial
            raise RuntimeError("Falha de importação simulada")

        with patch.dict(assets._IMPORTERS, {".glb": fail_after_creating_data}):
            with self.assertRaisesRegex(assets.AssetOperationError, "Falha de importação simulada"):
                assets.import_asset(bpy.context, str(path))

        self.assertEqual({item.as_pointer() for item in bpy.data.all_ids}, original_ids)
        self.assertCountEqual(assets.list_assets(bpy.context.scene), [asset])
        self.assertEqual(view_layer.active_layer_collection, active_layer)
        self.assertEqual(view_layer.objects.active, existing)
        self.assertEqual(bpy.context.selected_objects, [existing])

    def test_organization_correction_and_persistence(self):
        _, asset = self.import_fixture()
        first, second, *_ = sorted(assets.asset_objects(asset), key=lambda obj: obj.name)
        duplicate_name = "Peça revisada"
        self.assertEqual(assets.rename_mesh(first, duplicate_name), duplicate_name)
        corrected_name = assets.rename_mesh(second, duplicate_name)
        self.assertEqual(corrected_name, second.name)
        self.assertTrue(corrected_name.startswith(duplicate_name))
        self.assertNotEqual(corrected_name, first.name)
        with self.assertRaises(ValueError):
            assets.rename_mesh(second, "   ")
        self.assertEqual(second.name, corrected_name)

        external = bpy.data.collections.new("Referências do artista")
        bpy.context.scene.collection.children.link(external)
        external.objects.link(first)
        self.assertEqual(assets.category_for(first), "unidentified")
        assets.set_category(first, "skin")
        assets.set_category(second, "eyes")
        self.assertEqual(assets.organize_meshes(asset), 4)
        skin = self.category_collection(asset, first)
        self.assertEqual(assets.organize_meshes(asset), 4)
        self.assertEqual(self.category_collection(asset, first), skin)
        self.assertIn(first, external.objects[:])
        self.assertNotIn(first, asset.objects[:])

        with self.assertRaises(ValueError):
            assets.set_category(first, "categoria-inexistente")
        self.assertEqual(assets.category_for(first), "skin")
        assets.set_category(first, "hair")
        self.assertEqual(assets.organize_meshes(asset), 4)
        self.assertNotEqual(self.category_collection(asset, first), skin)
        self.assertIn(first, external.objects[:])
        assets.select_mesh(bpy.context, first)
        self.assertEqual(bpy.context.view_layer.objects.active, first)
        self.assertEqual(bpy.context.selected_objects, [first])

        identity = assets.asset_identity(asset)
        external_name = external.name
        project = self.directory / "Revisão.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(project))
        bpy.ops.wm.open_mainfile(filepath=str(project))
        (restored_asset,) = assets.list_assets(bpy.context.scene)
        self.assertEqual(assets.asset_identity(restored_asset), identity)
        restored_objects = {obj.name: obj for obj in assets.asset_objects(restored_asset)}
        self.assertEqual(len(restored_objects), 4)
        restored_mesh = restored_objects[duplicate_name]
        self.assertEqual(assets.category_for(restored_mesh), "hair")
        self.assertEqual(assets.category_for(restored_objects[corrected_name]), "eyes")
        self.assertIn(restored_mesh, bpy.data.collections[external_name].objects[:])
        self.category_collection(restored_asset, restored_mesh)

    def test_organization_preserves_imported_hierarchy_and_transforms(self):
        path = self.directory / "Peças agrupadas.glb"
        write_fixture(path, mesh_count=2, group_parts=True)
        asset = assets.import_asset(bpy.context, str(path))
        objects = assets.asset_objects(asset)
        (parent,) = (obj for obj in objects if obj.type == "EMPTY")
        meshes = [obj for obj in objects if obj.type == "MESH"]
        self.assertEqual(len(meshes), 2)
        self.assertTrue(all(obj.parent == parent for obj in meshes))
        bpy.context.view_layer.update()
        original_world_matrices = {obj.name: obj.matrix_world.copy() for obj in objects}

        assets.set_category(meshes[0], "metal")
        self.assertEqual(assets.organize_meshes(asset), 2)
        self.assertIn(parent, asset.objects[:])
        self.assertTrue(all(obj.parent == parent for obj in meshes))
        bpy.context.view_layer.update()
        for obj in objects:
            self.assertEqual(obj.matrix_world, original_world_matrices[obj.name])

    def test_original_and_evaluated_mesh_with_uv_material_and_armature(self):
        _, asset = self.import_fixture(mesh_count=2)
        mesh, other_mesh = sorted(assets.asset_objects(asset), key=lambda obj: obj.name)
        material = bpy.data.materials.new("Material sintético compartilhado")
        mesh.data.materials.append(material)
        other_mesh.data.materials.append(material)
        mesh.data.uv_layers.new(name="UV Sintético")
        armature = bpy.data.objects.new("Esqueleto Sintético", bpy.data.armatures.new("Juntas Sintéticas"))
        asset.objects.link(armature)
        mesh.parent = armature
        mesh.location = (0.0, 0.0, 0.0)
        mesh.scale = (2.0, 3.0, 4.0)
        modifier = mesh.modifiers.new("Repetição sintética", "ARRAY")
        modifier.count = 2
        armature_modifier = mesh.modifiers.new("Vínculo sintético", "ARMATURE")
        armature_modifier.object = armature
        bpy.context.view_layer.update()

        basic = analysis.analyze_asset(bpy.context, asset)
        self.assertIsNone(basic["summary"]["geometry_evaluated"])
        report = analysis.analyze_asset(bpy.context, asset, evaluated=True)
        summary = report["summary"]
        inventory = {item["name"]: item for item in report["meshes"]}
        inspected = inventory[mesh.name]
        self.assertEqual(summary["object_count"], 3)
        self.assertEqual(summary["mesh_count"], 2)
        self.assertEqual(summary["materials"], [material.name])
        self.assertEqual(summary["armatures"], [armature.name])
        self.assertTrue(summary["has_armature"])
        self.assertTrue(summary["has_modifiers"])
        self.assertEqual(summary["meshes_with_modifiers"], 1)
        self.assertEqual(summary["meshes_without_uv"], 1)
        self.assertEqual(summary["meshes_without_materials"], 0)
        self.assertEqual(summary["geometry_original"]["vertices"], 16)
        self.assertEqual(summary["geometry_evaluated"]["vertices"], 24)
        self.assertEqual(inspected["geometry_original"]["vertices"], 8)
        self.assertEqual(inspected["geometry_evaluated"]["vertices"], 16)
        self.assertEqual(inspected["geometry_original"]["dimensions"], [1.0, 1.0, 1.0])
        self.assertEqual(inspected["geometry_evaluated"]["dimensions"], [2.0, 1.0, 1.0])
        self.assertEqual(inspected["geometry_original"]["uv_layers"], ["UV Sintético"])
        self.assertEqual(inspected["geometry_evaluated"]["uv_layers"], ["UV Sintético"])
        self.assertEqual(inspected["materials"], [material.name])
        self.assertEqual(inspected["armatures"], [armature.name])
        self.assertEqual(
            [(entry["name"], entry["type"]) for entry in inspected["modifiers"]],
            [(modifier.name, "ARRAY"), (armature_modifier.name, "ARMATURE")],
        )
        self.assertEqual(len(mesh.data.vertices), 8)
        self.assertEqual(len(mesh.modifiers), 2)
        self.assertEqual(mesh.parent, armature)

    def test_excluded_collection_reports_unavailable_evaluated_geometry(self):
        _, asset = self.import_fixture(mesh_count=1)
        bpy.context.view_layer.layer_collection.children[asset.name].exclude = True
        report = analysis.analyze_asset(bpy.context, asset, evaluated=True)
        self.assertEqual(report["summary"]["geometry_original"]["vertices"], 8)
        self.assertIsNone(report["summary"]["geometry_evaluated"])
        self.assertIsNone(report["meshes"][0]["geometry_evaluated"])
        self.assertIn("evaluation_unavailable", {issue["code"] for issue in report["issues"]})

    def test_registration_and_public_operators(self):
        arvertes_studio.register()
        self.addCleanup(arvertes_studio.unregister)
        arvertes_studio.register()
        self.assertTrue(hasattr(bpy.types.Scene, "arvertes_studio"))
        self.assertTrue(hasattr(bpy.types, "ARVERTES_STUDIO_PT_main"))
        path = self.directory / "Fluxo da interface.glb"
        write_fixture(path, mesh_count=2)
        self.assertEqual(bpy.ops.arvertes_studio.import_glb(filepath=str(path)), {"FINISHED"})
        state = bpy.context.scene.arvertes_studio
        self.assertIn(state.asset, assets.list_assets(bpy.context.scene))
        state.mesh_index = 0
        self.assertEqual(bpy.ops.arvertes_studio.select_mesh(), {"FINISHED"})
        mesh = bpy.context.view_layer.objects.active
        self.assertIn(mesh, assets.asset_objects(state.asset))
        self.assertEqual(bpy.ops.arvertes_studio.rename_mesh(name="Peça editada"), {"FINISHED"})
        self.assertEqual(mesh.name, "Peça editada")
        self.assertEqual(bpy.ops.arvertes_studio.classify_mesh(category="accessories"), {"FINISHED"})
        self.assertEqual(assets.category_for(mesh), "accessories")
        self.assertEqual(bpy.ops.arvertes_studio.organize_meshes(), {"FINISHED"})
        state.include_evaluated = True
        self.assertEqual(bpy.ops.arvertes_studio.analyze_asset(), {"FINISHED"})
        target = self.directory / "Relatório da interface.json"
        self.assertEqual(bpy.ops.arvertes_studio.export_report(filepath=str(target)), {"FINISHED"})
        report = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(report["summary"]["mesh_count"], 2)
        self.assertIsNotNone(report["summary"]["geometry_evaluated"])
        self.assertEqual(
            next(item["category"] for item in report["meshes"] if item["name"] == mesh.name),
            "accessories",
        )
        self.assertEqual(ui._get_analysis(bpy.context, state.asset, True), report)
        alternate = bpy.context.scene.view_layers.new("Camada alternativa")
        with bpy.context.temp_override(view_layer=alternate):
            self.assertIsNone(ui._get_analysis(bpy.context, state.asset, True))
        self.assertEqual(ui._get_analysis(bpy.context, state.asset, True), report)
        arvertes_studio.unregister()
        arvertes_studio.unregister()
        self.assertFalse(hasattr(bpy.types.Scene, "arvertes_studio"))
        self.assertFalse(hasattr(bpy.types, "ARVERTES_STUDIO_PT_main"))
        arvertes_studio.register()
        self.assertTrue(hasattr(bpy.types.Scene, "arvertes_studio"))


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(BlenderIntegrationTests)
    if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
        raise RuntimeError("Falha nos testes de integração do Arvertes Studio.")
