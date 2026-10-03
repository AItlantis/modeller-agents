from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import modeller.runtime as runtime
from modeller.runtime import discover_workspace_source_roots


class WorkspaceSourceDiscoveryTests(unittest.TestCase):
    def test_discovery_skips_permission_denied_anchors_and_children(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            consumer = workspace / "consumer"
            source = workspace / "modelling-knowledge"
            inaccessible_child = workspace / "systemd-private-protected"
            consumer.mkdir(parents=True)
            source.mkdir()
            inaccessible_child.mkdir()
            (source / "README.md").write_text("# source root\n", encoding="utf-8")

            original_iterdir = Path.iterdir
            original_is_dir = Path.is_dir
            denied_anchors: list[Path] = []
            denied_children: list[Path] = []

            def guarded_iterdir(path: Path):
                if path.name == consumer.name and path.parent.name == workspace.name:
                    denied_anchors.append(path)
                    raise PermissionError("fixture denies listing this anchor")
                return original_iterdir(path)

            def guarded_is_dir(path: Path) -> bool:
                if path.name == inaccessible_child.name:
                    denied_children.append(path)
                    raise PermissionError("fixture denies inspecting this child")
                return original_is_dir(path)

            with (
                patch.object(Path, "iterdir", guarded_iterdir),
                patch.object(Path, "is_dir", guarded_is_dir),
            ):
                discovered = discover_workspace_source_roots(consumer, "modelling-knowledge")

            self.assertEqual(discovered, [source.resolve()])
            self.assertTrue(denied_anchors, "the inaccessible anchor must be exercised")
            self.assertTrue(denied_children, "the inaccessible child must be exercised")

    def test_discovery_skips_permission_denied_source_root_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer = Path(tmp) / "consumer"
            source = consumer / "modelling-knowledge"
            source.mkdir(parents=True)
            (source / "README.md").write_text("# source root\n", encoding="utf-8")
            original_check = runtime._looks_like_source_root
            checked_paths: list[Path] = []

            def guarded_source_check(path: Path, target_repository: str) -> bool:
                if path.name == source.name and path.parent.name == consumer.name:
                    checked_paths.append(path)
                    raise PermissionError("fixture denies source-root inspection")
                return original_check(path, target_repository)

            with patch.object(runtime, "_looks_like_source_root", guarded_source_check):
                discovered = discover_workspace_source_roots(consumer, "modelling-knowledge")

            self.assertEqual(discovered, [])
            self.assertTrue(checked_paths, "the inaccessible source-root check must be exercised")


if __name__ == "__main__":
    unittest.main()
