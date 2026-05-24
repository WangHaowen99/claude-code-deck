import importlib.util
from importlib.machinery import SourceFileLoader
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CCD_PATH = ROOT / "ccd"


def load_ccd():
    loader = SourceFileLoader("ccd_module", str(CCD_PATH))
    spec = importlib.util.spec_from_loader("ccd_module", loader)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_transcript(path: Path, mtime: datetime) -> None:
    path.write_text('{"type":"assistant","message":{"content":"done"}}\n', encoding="utf-8")
    timestamp = mtime.timestamp()
    os.utime(path, (timestamp, timestamp))


def write_events(path: Path, events: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")


class CcdTests(unittest.TestCase):
    def setUp(self):
        self.ccd = load_ccd()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.configure_paths()

    def tearDown(self):
        self.tmp.cleanup()

    def configure_paths(self):
        ccd = self.ccd
        ccd.CONFIG_DIR = self.root / "config"
        ccd.DATA_DIR = self.root / "data"
        ccd.STATE_DIR = self.root / "state"
        ccd.CONFIG_PATH = ccd.CONFIG_DIR / "config.json"
        ccd.REGISTRY_PATH = ccd.DATA_DIR / "sessions.json"
        ccd.LOCK_PATH = ccd.STATE_DIR / "lock"
        ccd.LOG_PATH = ccd.STATE_DIR / "ccd.log"
        ccd.CLAUDE_HOME = self.root / "claude"
        ccd.CLAUDE_SETTINGS_PATH = ccd.CLAUDE_HOME / "settings.json"
        ccd.CLAUDE_HISTORY_PATH = ccd.CLAUDE_HOME / "history.jsonl"
        ccd.CLAUDE_PROJECTS_DIR = ccd.CLAUDE_HOME / "projects"

    def test_install_settings_hook_preserves_settings_and_replaces_old_ccd_hook(self):
        self.ccd.CLAUDE_SETTINGS_PATH.parent.mkdir(parents=True)
        self.ccd.CLAUDE_SETTINGS_PATH.write_text(
            json.dumps(
                {
                    "theme": "dark",
                    "hooks": {
                        "SessionStart": [
                            {
                                "matcher": "old",
                                "hooks": [{"type": "command", "command": "/old/ccd __hook-session-start"}],
                            },
                            {
                                "matcher": ".*",
                                "hooks": [{"type": "command", "command": "echo keep"}],
                            },
                        ]
                    },
                }
            ),
            encoding="utf-8",
        )
        self.ccd.current_ccd_path = lambda: "/tmp/bin/ccd"

        self.ccd.install_settings_hook()

        settings = json.loads(self.ccd.CLAUDE_SETTINGS_PATH.read_text(encoding="utf-8"))
        self.assertEqual(settings["theme"], "dark")
        groups = settings["hooks"]["SessionStart"]
        commands = [hook["command"] for group in groups for hook in group["hooks"]]
        self.assertIn("echo keep", commands)
        self.assertEqual(commands.count("/tmp/bin/ccd __hook-session-start"), 1)
        self.assertEqual(groups[-1]["matcher"], "^(startup|resume)$")

    def test_session_start_hook_records_claude_session(self):
        self.ccd.ensure_dirs()
        registry = {
            "version": self.ccd.VERSION,
            "sessions": [
                {
                    "id": "deck1",
                    "name": "work",
                    "tmux_session": "ccd_deck1",
                    "claude_session_id": None,
                    "last_cwd": str(self.root),
                    "created_at": "2026-05-09T00:00:00Z",
                    "updated_at": "2026-05-09T00:00:00Z",
                    "last_used_at": "2026-05-09T00:00:00Z",
                    "transcript_path": None,
                }
            ],
        }
        self.ccd.save_registry(registry)
        payload = {
            "session_id": "11111111-1111-4111-8111-111111111111",
            "cwd": str(self.root / "project"),
            "transcript_path": str(self.root / "project.jsonl"),
            "source": "startup",
        }

        with mock.patch.dict(os.environ, {"CCD_SESSION_ID": "deck1"}), mock.patch.object(sys, "stdin", io.StringIO(json.dumps(payload))):
            rc = self.ccd.cmd_hook_session_start([])

        self.assertEqual(rc, 0)
        saved = self.ccd.load_registry()["sessions"][0]
        self.assertEqual(saved["claude_session_id"], payload["session_id"])
        self.assertEqual(saved["last_cwd"], payload["cwd"])
        self.assertEqual(saved["transcript_path"], payload["transcript_path"])

    def test_load_claude_sessions_reads_history_and_project_transcripts(self):
        sid = "22222222-2222-4222-8222-222222222222"
        self.ccd.CLAUDE_HISTORY_PATH.parent.mkdir(parents=True)
        self.ccd.CLAUDE_HISTORY_PATH.write_text(
            json.dumps({"sessionId": sid, "display": "build a deck", "timestamp": 1778240000000, "project": str(self.root / "repo")}) + "\n",
            encoding="utf-8",
        )
        transcript_dir = self.ccd.CLAUDE_PROJECTS_DIR / "-root-repo"
        transcript_dir.mkdir(parents=True)
        transcript_path = transcript_dir / f"{sid}.jsonl"
        transcript_path.write_text(
            "\n".join(
                [
                    json.dumps({"type": "permission-mode", "sessionId": sid}),
                    json.dumps(
                        {
                            "type": "user",
                            "sessionId": sid,
                            "cwd": str(self.root / "repo"),
                            "timestamp": "2026-05-09T01:02:03Z",
                            "message": {"role": "user", "content": "hello from transcript"},
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        sessions = self.ccd.load_claude_sessions()

        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].id, sid)
        self.assertEqual(sessions[0].title, "build a deck")
        self.assertEqual(sessions[0].cwd, str(self.root / "repo"))
        self.assertEqual(sessions[0].transcript_path, str(transcript_path))
        self.assertEqual(sessions[0].updated_at, "2026-05-09T01:02:03Z")

    def test_runner_uses_claude_resume_option_for_bound_session(self):
        self.ccd.ensure_dirs()
        sid = "33333333-3333-4333-8333-333333333333"
        self.ccd.save_registry(
            {
                "version": self.ccd.VERSION,
                "sessions": [
                    {
                        "id": "deck1",
                        "name": "work",
                        "tmux_session": "ccd_deck1",
                        "claude_session_id": sid,
                        "last_cwd": str(self.root),
                        "created_at": "2026-05-09T00:00:00Z",
                        "updated_at": "2026-05-09T00:00:00Z",
                        "last_used_at": "2026-05-09T00:00:00Z",
                        "transcript_path": None,
                    }
                ],
            }
        )
        seen = []

        def fake_run(args, env=None):
            seen.append((args, env))
            return subprocess.CompletedProcess(args, 0)

        with mock.patch.object(self.ccd.subprocess, "run", fake_run):
            rc = self.ccd.cmd_runner(["deck1"])

        self.assertEqual(rc, 0)
        self.assertEqual(seen[0][0], ["claude", "--resume", sid, "--effort", "max"])
        self.assertEqual(seen[0][1]["CCD_SESSION_ID"], "deck1")

    def test_unbound_session_is_never_unread(self):
        session = {
            "id": "deck1",
            "name": "work",
            "tmux_session": "ccd_deck1",
            "claude_session_id": None,
        }

        self.assertFalse(self.ccd.session_has_unread_result(session))

    def test_transcript_newer_than_last_viewed_is_unread(self):
        transcript = self.root / "session.jsonl"
        write_transcript(transcript, datetime(2026, 5, 9, 8, 30, tzinfo=timezone.utc))
        session = {
            "id": "deck1",
            "name": "work",
            "tmux_session": "ccd_deck1",
            "claude_session_id": "claude-1",
            "transcript_path": str(transcript),
            "last_viewed_at": "2026-05-09T08:00:00Z",
        }

        self.assertTrue(self.ccd.session_has_unread_result(session))

    def test_session_json_includes_view_state(self):
        transcript = self.root / "session.jsonl"
        write_transcript(transcript, datetime(2026, 5, 9, 8, 30, tzinfo=timezone.utc))
        session = {
            "id": "deck1",
            "name": "work",
            "tmux_session": "ccd_deck1",
            "claude_session_id": "claude-1",
            "transcript_path": str(transcript),
            "last_viewed_at": "2026-05-09T08:00:00Z",
        }

        data = self.ccd.session_json(session, include_status=False)

        self.assertTrue(data["unread"])
        self.assertEqual(data["last_viewed_at"], "2026-05-09T08:00:00Z")
        self.assertIsNotNone(data["conversation_updated_at"])

    def test_touch_last_used_can_mark_conversation_viewed(self):
        self.ccd.ensure_dirs()
        transcript = self.root / "session.jsonl"
        write_transcript(transcript, datetime(2026, 5, 9, 8, 30, tzinfo=timezone.utc))
        self.ccd.save_registry(
            {
                "version": self.ccd.VERSION,
                "sessions": [
                    {
                        "id": "deck1",
                        "name": "work",
                        "tmux_session": "ccd_deck1",
                        "claude_session_id": "claude-1",
                        "last_cwd": str(self.root),
                        "created_at": "2026-05-09T07:00:00Z",
                        "updated_at": "2026-05-09T07:00:00Z",
                        "last_used_at": "2026-05-09T07:00:00Z",
                        "last_viewed_at": "2026-05-09T08:00:00Z",
                        "transcript_path": str(transcript),
                    }
                ],
            }
        )

        self.ccd.touch_last_used("deck1", mark_viewed=True)

        saved = self.ccd.load_registry()["sessions"][0]
        self.assertFalse(self.ccd.session_has_unread_result(saved))
        self.assertEqual(
            saved["last_viewed_at"],
            self.ccd.later_time(saved["last_used_at"], self.ccd.session_conversation_updated_at(saved)),
        )

    def test_mark_viewed_command_clears_unread_state(self):
        self.ccd.ensure_dirs()
        transcript = self.root / "session.jsonl"
        write_transcript(transcript, datetime(2026, 5, 9, 8, 30, tzinfo=timezone.utc))
        self.ccd.save_registry(
            {
                "version": self.ccd.VERSION,
                "sessions": [
                    {
                        "id": "deck1",
                        "name": "work",
                        "tmux_session": "ccd_deck1",
                        "claude_session_id": "claude-1",
                        "last_cwd": str(self.root),
                        "created_at": "2026-05-09T07:00:00Z",
                        "updated_at": "2026-05-09T08:00:00Z",
                        "last_used_at": "2026-05-09T08:00:00Z",
                        "last_viewed_at": "2026-05-09T08:00:00Z",
                        "transcript_path": str(transcript),
                    }
                ],
            }
        )

        self.assertTrue(self.ccd.session_has_unread_result(self.ccd.load_registry()["sessions"][0]))
        output = io.StringIO()
        with redirect_stdout(output):
            rc = self.ccd.cmd_mark_viewed(["--json", "work"])

        self.assertEqual(rc, 0)
        payload = json.loads(output.getvalue())
        self.assertTrue(payload["ok"])
        refreshed = self.ccd.load_registry()["sessions"][0]
        self.assertFalse(self.ccd.session_has_unread_result(refreshed))
        self.assertGreaterEqual(
            self.ccd.sort_key_time(refreshed["last_viewed_at"]),
            self.ccd.sort_key_time(self.ccd.session_conversation_updated_at(refreshed)),
        )

    def test_activity_state_reports_running_elapsed_time(self):
        transcript = self.root / "session.jsonl"
        write_events(
            transcript,
            [
                {"timestamp": "2026-05-09T08:00:00Z", "type": "user", "message": {"role": "user", "content": "build"}},
                {
                    "timestamp": "2026-05-09T08:01:00Z",
                    "type": "assistant",
                    "message": {"role": "assistant", "stop_reason": "tool_use"},
                },
            ],
        )
        session = {
            "id": "deck1",
            "name": "work",
            "tmux_session": "ccd_deck1",
            "claude_session_id": "claude-1",
            "transcript_path": str(transcript),
            "last_viewed_at": "2026-05-09T07:00:00Z",
        }

        with mock.patch.object(self.ccd, "tmux_exists", return_value=True):
            state = self.ccd.session_activity(session, now=self.ccd.parse_iso("2026-05-09T08:03:30Z"))

        self.assertEqual(state["state"], "running")
        self.assertEqual(state["started_at"], "2026-05-09T08:00:00Z")
        self.assertEqual(state["elapsed_seconds"], 210)

    def test_activity_state_falls_back_to_unread_after_turn_complete(self):
        transcript = self.root / "session.jsonl"
        write_events(
            transcript,
            [
                {"timestamp": "2026-05-09T08:00:00Z", "type": "user", "message": {"role": "user", "content": "build"}},
                {
                    "timestamp": "2026-05-09T08:03:00Z",
                    "type": "assistant",
                    "message": {"role": "assistant", "stop_reason": "end_turn"},
                },
            ],
        )
        timestamp = self.ccd.parse_iso("2026-05-09T08:03:00Z").timestamp()
        os.utime(transcript, (timestamp, timestamp))
        session = {
            "id": "deck1",
            "name": "work",
            "tmux_session": "ccd_deck1",
            "claude_session_id": "claude-1",
            "transcript_path": str(transcript),
            "last_viewed_at": "2026-05-09T07:00:00Z",
        }

        with mock.patch.object(self.ccd, "tmux_exists", return_value=True):
            state = self.ccd.session_activity(session, now=self.ccd.parse_iso("2026-05-09T08:04:00Z"))

        self.assertEqual(state["state"], "unread")
        self.assertIsNone(state["elapsed_seconds"])

    def test_session_json_resolves_missing_transcript_path_from_claude_projects(self):
        sid = "44444444-4444-4444-8444-444444444444"
        transcript_dir = self.ccd.CLAUDE_PROJECTS_DIR / "-tmp"
        transcript_dir.mkdir(parents=True)
        transcript = transcript_dir / f"{sid}.jsonl"
        write_transcript(transcript, datetime(2026, 5, 11, 2, 30, tzinfo=timezone.utc))
        session = {
            "id": "deck1",
            "name": "work",
            "tmux_session": "ccd_deck1",
            "claude_session_id": sid,
            "transcript_path": None,
            "last_viewed_at": "2026-05-11T02:24:30Z",
        }

        with mock.patch.object(self.ccd, "tmux_exists", return_value=False):
            data = self.ccd.session_json(session, include_status=False)

        self.assertEqual(data["transcript_path"], str(transcript))
        self.assertEqual(data["conversation_updated_at"], "2026-05-11T02:30:00Z")
        self.assertTrue(data["unread"])

    def test_hook_session_start_resolves_missing_transcript_path(self):
        self.ccd.ensure_dirs()
        sid = "55555555-5555-4555-8555-555555555555"
        transcript_dir = self.ccd.CLAUDE_PROJECTS_DIR / "-tmp"
        transcript_dir.mkdir(parents=True)
        transcript = transcript_dir / f"{sid}.jsonl"
        write_transcript(transcript, datetime(2026, 5, 11, 2, 30, tzinfo=timezone.utc))
        self.ccd.save_registry(
            {
                "version": self.ccd.VERSION,
                "sessions": [
                    {
                        "id": "deck1",
                        "name": "work",
                        "tmux_session": "ccd_deck1",
                        "claude_session_id": None,
                        "last_cwd": str(self.root),
                        "created_at": "2026-05-11T02:24:30Z",
                        "updated_at": "2026-05-11T02:24:30Z",
                        "last_used_at": "2026-05-11T02:24:30Z",
                        "last_viewed_at": "2026-05-11T02:24:30Z",
                        "transcript_path": None,
                    }
                ],
            }
        )
        payload = {"session_id": sid, "cwd": str(self.root), "source": "startup"}

        with mock.patch.dict(os.environ, {"CCD_SESSION_ID": "deck1"}), mock.patch.object(sys, "stdin", io.StringIO(json.dumps(payload))):
            rc = self.ccd.cmd_hook_session_start([])

        self.assertEqual(rc, 0)
        saved = self.ccd.load_registry()["sessions"][0]
        self.assertEqual(saved["transcript_path"], str(transcript))

    def test_closed_sessions_are_hidden_from_active_list_and_reopenable(self):
        self.ccd.ensure_dirs()
        self.ccd.save_registry(
            {
                "version": self.ccd.VERSION,
                "sessions": [
                    {
                        "id": "deck1",
                        "name": "work",
                        "tmux_session": "ccd_deck1",
                        "claude_session_id": "claude-1",
                        "last_cwd": str(self.root),
                        "created_at": "2026-05-09T00:00:00Z",
                        "updated_at": "2026-05-09T00:00:00Z",
                        "last_used_at": "2026-05-09T00:00:00Z",
                        "transcript_path": None,
                    }
                ],
            }
        )

        with mock.patch.object(self.ccd, "tmux_exists", return_value=False):
            output = io.StringIO()
            with redirect_stdout(output):
                close_rc = self.ccd.cmd_close(["--yes", "--json", "work"])
            list_payload = json.loads(self.capture_stdout(lambda: self.ccd.cmd_list(["--json"])))
            history_payload = json.loads(self.capture_stdout(lambda: self.ccd.cmd_history(["--json"])))
            reopen_output = io.StringIO()
            with redirect_stdout(reopen_output):
                reopen_rc = self.ccd.cmd_reopen(["--json", "work"])

        self.assertEqual(close_rc, 0)
        self.assertEqual(reopen_rc, 0)
        self.assertEqual(list_payload["sessions"], [])
        self.assertEqual(history_payload["sessions"][0]["name"], "work")
        self.assertIn("closed_at", history_payload["sessions"][0])
        self.assertNotIn("closed_at", self.ccd.load_registry()["sessions"][0])

    def test_new_refuses_closed_duplicate_name(self):
        self.ccd.ensure_dirs()
        self.ccd.save_registry(
            {
                "version": self.ccd.VERSION,
                "sessions": [
                    {
                        "id": "deck1",
                        "name": "work",
                        "tmux_session": "ccd_deck1",
                        "claude_session_id": "claude-1",
                        "last_cwd": str(self.root),
                        "created_at": "2026-05-09T00:00:00Z",
                        "updated_at": "2026-05-09T00:00:00Z",
                        "last_used_at": "2026-05-09T00:00:00Z",
                        "closed_at": "2026-05-10T00:00:00Z",
                        "transcript_path": None,
                    }
                ],
            }
        )

        with mock.patch.object(self.ccd, "require_tool"), redirect_stdout(io.StringIO()):
            rc = self.ccd.cmd_new(["--cwd", str(self.root), "--no-enter", "--json", "work"])

        self.assertEqual(rc, 1)

    def test_fork_creates_new_session_from_bound_source(self):
        self.ccd.ensure_dirs()
        self.ccd.save_registry(
            {
                "version": self.ccd.VERSION,
                "sessions": [
                    {
                        "id": "deck1",
                        "name": "work",
                        "tmux_session": "ccd_deck1",
                        "claude_session_id": "claude-1",
                        "last_cwd": str(self.root),
                        "created_at": "2026-05-09T00:00:00Z",
                        "updated_at": "2026-05-09T00:00:00Z",
                        "last_used_at": "2026-05-09T00:00:00Z",
                        "transcript_path": None,
                    }
                ],
            }
        )

        with mock.patch.object(self.ccd, "require_tool"), redirect_stdout(io.StringIO()):
            rc = self.ccd.cmd_fork(["--no-enter", "--json", "work", "branch"])

        self.assertEqual(rc, 0)
        created = self.ccd.find_session_by_name(self.ccd.load_registry(), "branch")
        self.assertIsNotNone(created)
        self.assertEqual(created["fork_from_claude_session_id"], "claude-1")
        self.assertEqual(created["fork_from_ccd_id"], "deck1")
        self.assertEqual(self.ccd.claude_args_for_session(created), ["claude", "--resume", "claude-1", "--fork-session", "--effort", "max"])

    def capture_stdout(self, fn):
        output = io.StringIO()
        with redirect_stdout(output):
            rc = fn()
        self.assertEqual(rc, 0)
        return output.getvalue()


if __name__ == "__main__":
    unittest.main()
