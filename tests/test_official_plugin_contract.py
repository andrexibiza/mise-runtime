import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "hermes-plugin"))

import mise
from mise import MiseMemoryProvider


class Collector:
    def __init__(self):
        self.provider = None

    def register_memory_provider(self, provider):
        self.provider = provider


class OfficialPluginContractTests(unittest.TestCase):
    def test_register_entrypoint_exposes_mise_provider(self):
        collector = Collector()
        mise.register(collector)
        self.assertIsInstance(collector.provider, MiseMemoryProvider)
        self.assertEqual(collector.provider.name, "mise")

    def test_availability_is_local_only_and_requires_data_source_configuration(self):
        provider = MiseMemoryProvider()
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(provider.is_available())
        with patch.dict(os.environ, {"MISE_DATA_SOURCE_URL": "collection://00000000-0000-4000-8000-000000000001"}, clear=True):
            self.assertTrue(provider.is_available())

    def test_initialize_fails_closed_when_path_home_is_unavailable(self):
        provider = MiseMemoryProvider()

        with patch.dict(os.environ, {}, clear=True):
            with patch("mise.Path.home", side_effect=RuntimeError("home unavailable")):
                provider.initialize("session-1")

        self.assertFalse(provider.active)
        self.assertEqual(provider.hermes_home, "")

    def test_setup_schema_declares_data_source(self):
        provider = MiseMemoryProvider()
        fields = {field["key"]: field for field in provider.get_config_schema()}
        self.assertIn("data_source_url", fields)
        self.assertTrue(fields["data_source_url"]["required"])
        self.assertFalse(fields["data_source_url"].get("secret", False))

    def test_save_config_is_profile_scoped(self):
        provider = MiseMemoryProvider()
        with tempfile.TemporaryDirectory() as td:
            provider.save_config({"data_source_url": "collection://00000000-0000-4000-8000-000000000001"}, td)
            saved = json.loads((Path(td) / "mise.json").read_text())
        self.assertEqual(saved["data_source_url"], "collection://00000000-0000-4000-8000-000000000001")

    def test_real_loader_activates_from_profile_config_without_environment_override(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            destination = home / "plugins" / "mise"
            destination.parent.mkdir(parents=True)
            shutil.copytree(Path(__file__).parents[1] / "hermes-plugin" / "mise", destination)
            (home / "mise.json").write_text(
                json.dumps({"data_source_url": "collection://00000000-0000-4000-8000-000000000001"}),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["HERMES_HOME"] = td
            env.pop("MISE_DATA_SOURCE_URL", None)
            subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "from plugins.memory import load_memory_provider; "
                        "p = load_memory_provider('mise'); "
                        "assert p is not None and p.is_available(); "
                        "assert p.data_source_url == "
                        "'collection://00000000-0000-4000-8000-000000000001'"
                    ),
                ],
                check=True,
                cwd=Path(__file__).parents[1],
                env=env,
            )

    def test_prompt_does_not_treat_designation_or_declared_authority_as_truth(self):
        provider = MiseMemoryProvider()
        provider.active = True
        text = provider.system_prompt_block().lower()
        self.assertIn("does not prove", text)
        self.assertIn("current evidence", text)
        self.assertNotIn("canonical durable memory provider", text)


if __name__ == "__main__":
    unittest.main()
