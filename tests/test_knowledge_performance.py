"""Regression checks for unchanged sources and completion-based worker scheduling."""
from contextlib import ExitStack
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import knowledge_collect as collect
import knowledge_worker


class SourcePathTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.projects = [
            {'workspace': str(self.root / f'project-{index}'), 'id': str(index)}
            for index in range(87)
        ]
        self.roots = [project['workspace'] for project in self.projects]
        self.file = self.root / 'project-0/document.md'
        self.file.parent.mkdir()
        self.file.write_text('Synthetic source', encoding='utf-8')

    def test_repeated_safe_path_reuses_lexical_roots(self):
        collect.safe_path(self.file, self.roots)
        with patch.object(collect, 'Path', wraps=Path) as constructed:
            self.assertEqual(collect.safe_path(self.file, self.roots), self.file.resolve())
        self.assertLessEqual(constructed.call_count, 2)

    def test_repeated_scope_reuses_lexical_project_paths(self):
        config = {'shared_workspace_roots': []}
        collect.scope_for(str(self.file.parent), self.projects, config)
        with patch.object(collect, 'Path', wraps=Path) as constructed:
            self.assertEqual(collect.scope_for(str(self.file.parent), self.projects, config), '0')
        self.assertLessEqual(constructed.call_count, 2)

    def test_cached_paths_keep_live_link_checks(self):
        collect.safe_path(self.file, self.roots)
        with patch.object(Path, 'is_symlink', return_value=True):
            with self.assertRaisesRegex(ValueError, 'junction'):
                collect.safe_path(self.file, self.roots)

    def test_updated_roots_and_project_identity_take_effect(self):
        collect.safe_path(self.file, self.roots)
        with self.assertRaises(ValueError):
            collect.safe_path(self.file, self.roots[1:])
        config = {'shared_workspace_roots': []}
        collect.scope_for(str(self.file.parent), self.projects, config)
        self.projects[0]['id'] = 'new-owner'
        self.assertEqual(collect.scope_for(str(self.file.parent), self.projects, config), 'new-owner')

    def test_relative_roots_follow_current_directory(self):
        original = Path.cwd()
        other = self.root / 'other'
        other_file = other / 'project-0/document.md'
        other_file.parent.mkdir(parents=True)
        other_file.write_text('Other synthetic source', encoding='utf-8')
        try:
            os.chdir(self.root)
            first = collect.safe_path('project-0/document.md', ['project-0'])
            os.chdir(other)
            second = collect.safe_path('project-0/document.md', ['project-0'])
        finally:
            os.chdir(original)
        self.assertEqual(first, self.file.resolve())
        self.assertEqual(second, other_file.resolve())

    def test_matching_name_prefix_does_not_select_sibling_directory(self):
        sibling = self.root / 'project-01/document.md'
        with self.assertRaises(ValueError):
            collect.safe_path(sibling, [self.roots[0]])
        self.assertIsNone(collect.scope_for(str(sibling.parent), self.projects[:1],
                                            {'shared_workspace_roots': []}))

    @unittest.skipUnless(os.name == 'nt', 'Windows paths are case-insensitive')
    def test_windows_root_spelling_remains_case_insensitive(self):
        roots = [root.swapcase() for root in self.roots]
        self.assertEqual(collect.safe_path(self.file, roots), self.file.resolve())
        projects = [{'workspace': project['workspace'].swapcase(), 'id': project['id']}
                    for project in self.projects]
        self.assertEqual(collect.scope_for(str(self.file.parent), projects,
                                           {'shared_workspace_roots': []}), '0')


class WorkerScheduleTests(unittest.TestCase):
    def check_completion_interval(self, attribute, operation, interval, fails=False):
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as patches:
            directory = Path(temporary)
            values = {'collector_policy': 3}
            connection = MagicMock()
            connection.return_value.__enter__.return_value.execute.return_value = []
            config = {'board_delivery': False, 'project_roots': [], 'reconcile_seconds': 180}
            if attribute == 'last_scan':
                config['project_roots'] = [{'path': temporary, 'project_id': 'project'}]
            hub = SimpleNamespace(
                config=config, config_path=directory / 'absent.json', notes=directory / 'notes',
                value=lambda key, default=None: values.get(key, default),
                set_value=lambda key, value: values.__setitem__(key, value), connect=connection)
            clock = patches.enter_context(patch.object(knowledge_worker.time, 'monotonic', return_value=1000.0))
            patches.enter_context(patch.object(knowledge_worker, 'below_normal', return_value=True))
            patches.enter_context(patch.object(knowledge_worker, 'windows_metrics', return_value=(
                {'cpu_percent': 0, 'available_mb': 4096, 'working_set_mb': 20}, None)))
            patches.enter_context(patch.object(knowledge_worker, 'recording_busy', return_value=False))
            for name in ('serve_commands', 'consume_signals', 'drain_one', 'snapshot_git'):
                patches.enter_context(patch.object(knowledge_worker, name, return_value=None))
            for name in ('mirror_board', 'discover_sessions', 'scan_documents'):
                patches.enter_context(patch.object(collect, name, return_value={}))
            worker = knowledge_worker.Worker(hub)
            for name in ('last_board', 'last_sessions', 'last_scan', 'last_git'):
                setattr(worker, name, 1_000_000.0)
            setattr(worker, attribute, 0)

            def slow_operation(*args, **kwargs):
                clock.return_value += interval + 1
                if fails and ran.call_count == 1:
                    raise RuntimeError('Synthetic background operation failure')
                return {}

            ran = patches.enter_context(patch(operation, side_effect=slow_operation))
            if fails:
                with self.assertRaisesRegex(RuntimeError, 'Synthetic'):
                    worker.tick()
            else:
                worker.tick()
            clock.return_value += 2
            worker.tick()
            self.assertEqual(ran.call_count, 1)

    def test_long_board_sweep_waits_after_completion(self):
        self.check_completion_interval('last_board', 'knowledge_collect.mirror_board', 60)

    def test_long_document_scan_waits_after_completion(self):
        self.check_completion_interval('last_scan', 'knowledge_collect.scan_documents', 180)

    def test_long_session_discovery_waits_after_completion(self):
        self.check_completion_interval('last_sessions', 'knowledge_collect.discover_sessions', 180)

    def test_long_git_snapshot_waits_after_completion(self):
        self.check_completion_interval('last_git', 'knowledge_worker.snapshot_git', 300)

    def test_failed_board_sweep_waits_before_retry(self):
        self.check_completion_interval('last_board', 'knowledge_collect.mirror_board', 60, fails=True)

    def test_failed_git_snapshot_waits_before_retry(self):
        self.check_completion_interval('last_git', 'knowledge_worker.snapshot_git', 300, fails=True)

    def test_failed_document_scan_waits_before_retry(self):
        self.check_completion_interval('last_scan', 'knowledge_collect.scan_documents', 180, fails=True)

    def test_failed_session_discovery_waits_before_retry(self):
        self.check_completion_interval('last_sessions', 'knowledge_collect.discover_sessions', 180, fails=True)


if __name__ == '__main__':
    unittest.main()
