from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from arvertes_desktop.generation_adapter import probe, validate_handoff
from arvertes_studio.core.character_style import study_presets, validate_adaptation, validate_style


class GenerationTests(TestCase):
    def test_study_presets_are_distinct_and_bounded(self):
        coral, cobre = (validate_style(value) for value in study_presets().values())
        self.assertGreater(coral["height_m"], cobre["height_m"])
        self.assertNotEqual(coral["palette"], cobre["palette"])
        with self.assertRaises(ValueError):
            validate_style({**coral, "height_m": float("nan")})
        with self.assertRaises(ValueError):
            validate_adaptation({"height_m": 7, "front": "-Y", "require_humanoid": False})

    def test_handoff_binds_artifact_license_and_input_hashes(self):
        model, reference = b"GLB binary from the Studio", "a" * 64
        metadata = {"schema":1,"provider":"local_authored","version":"v1","model_sha256":sha256(model).hexdigest(),
                    "references":[reference],"license":"Fixture experimental","cost_centavos":0}
        self.assertFalse(validate_handoff(metadata, model, [reference])["inference_verified_by_studio"])
        for invalid in ({"cost_centavos":1}, {"references":["b" * 64]}, {"license":""},
                        {"model_sha256":"c" * 64}, {"provider":["local_authored"]}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_handoff({**metadata, **invalid}, model, [reference])

    def test_missing_and_unapproved_generator_remains_unavailable(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp)
            status = probe(path / "absent", path / "weights", path / "python")
            self.assertEqual(status["state"], "unavailable")
            self.assertIn("operator_authorization_required", status["reasons"])
            self.assertIn("weights_missing", status["reasons"])
