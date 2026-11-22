import unittest

from arvertes_studio.core.classification import CATEGORY_LABELS, RuleClassifier


class RuleClassifierTests(unittest.TestCase):
    def setUp(self):
        self.classifier = RuleClassifier()

    def test_initial_categories_have_stable_codes_and_portuguese_labels(self):
        self.assertEqual(
            CATEGORY_LABELS,
            {
                "skin": "Pele",
                "hair": "Cabelo",
                "eyes": "Olhos",
                "clothing": "Roupas",
                "footwear": "Calçados",
                "accessories": "Acessórios",
                "metal": "Metal",
                "vegetation": "Vegetação",
                "buildings": "Construções",
                "creatures": "Criaturas",
                "objects": "Objetos",
                "unidentified": "Não identificado",
            },
        )

    def test_recognizes_each_category_through_name_tokens(self):
        examples = {
            "Pele02": "skin",
            "MeshTranças.001": "hair",
            "LEFT_EYE": "eyes",
            "MESH_Calça": "clothing",
            "mesh-calçados_02": "footwear",
            "Pulseira.Acabamento": "accessories",
            "MATAlumínio": "metal",
            "Árvore": "vegetation",
            "Roof.Tiles": "buildings",
            "Creature_mesh": "creatures",
            "Crate": "objects",
        }
        for name, category in examples.items():
            with self.subTest(name=name):
                result = self.classifier.suggest(name)
                self.assertEqual(result.category, category)
                self.assertTrue(result.evidence)

    def test_material_names_can_supply_evidence_for_generic_object(self):
        result = self.classifier.suggest("Mesh.001", ("MAT_Steel",))
        self.assertEqual(result.category, "metal")
        self.assertIn("material", result.evidence[0])
        self.assertIn("steel", result.evidence[0])
        self.assertIn("Metal", result.reason)

    def test_unknown_generic_and_partial_words_are_left_unidentified(self):
        for name in ("", "MeshBody.001", "chair", "eyebrowed", "pedal"):
            with self.subTest(name=name):
                result = self.classifier.suggest(name, ("Material.002",))
                self.assertEqual(result.category, "unidentified")
                self.assertTrue(result.reason)
                self.assertEqual(result.evidence, ())

    def test_conflicting_signals_leave_category_unidentified(self):
        result = self.classifier.suggest("Hair_01", ("MAT_Copper",))
        self.assertEqual(result.category, "unidentified")
        self.assertEqual(len(result.evidence), 2)
        self.assertIn("Cabelo", result.reason)
        self.assertIn("Metal", result.reason)

    def test_repeated_and_reordered_evidence_is_deterministic(self):
        original = self.classifier.suggest("Braids", ["Hair", "Hair.001", "Hair"])
        reordered = self.classifier.suggest("Braids", reversed(["Hair", "Hair.001"]))
        self.assertEqual(original, reordered)
        self.assertEqual(original.category, "hair")
        self.assertEqual(len(original.evidence), 3)


if __name__ == "__main__":
    unittest.main()
