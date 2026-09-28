"""Offline checks for the one-click Windows launcher."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import project_launcher as launcher


class LauncherTests(unittest.TestCase):
    def test_env_file_keeps_equal_sign_in_token(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, ".env").write_text(
                "LINE_CHANNEL_SECRET=secret\nLINE_CHANNEL_ACCESS_TOKEN=abc==\n",
                encoding="utf-8",
            )
            with patch.object(launcher, "ROOT", Path(directory)):
                values = launcher.env_file()
        self.assertEqual(values["LINE_CHANNEL_ACCESS_TOKEN"], "abc==")

    def test_tunnel_pattern_accepts_only_quick_tunnel_host(self):
        log = "https://plain.example.com https://my-new-tunnel.trycloudflare.com"
        self.assertEqual(launcher.TUNNEL_RE.findall(log),
                         ["https://my-new-tunnel.trycloudflare.com"])

    def test_health_identity_prevents_reusing_wrong_server(self):
        with patch.object(launcher, "http_json", return_value={"ok": True}):
            self.assertFalse(launcher.healthy("http://localhost/healthz", identify=True))
            self.assertTrue(launcher.healthy("http://localhost/healthz", identify=False))

    def test_existing_line_endpoint_is_reused_when_healthy(self):
        endpoint = "https://healthy.trycloudflare.com/webhook"
        with patch.object(launcher, "line_endpoint", return_value={"endpoint": endpoint}):
            with patch.object(launcher, "healthy", return_value=True):
                self.assertEqual(launcher.ensure_tunnel(8000, {"LINE_CHANNEL_ACCESS_TOKEN": "test"}, {}), endpoint)

    def test_stale_owned_tunnel_is_restarted_before_updating_line(self):
        state = {"cloudflared": {"pid": 123, "started": 1.0}}
        base = {"LINE_CHANNEL_ACCESS_TOKEN": "test"}
        with patch.object(launcher, "line_endpoint", return_value={
            "endpoint": "https://old.trycloudflare.com/webhook"
        }), patch.object(launcher, "healthy", side_effect=[False, False, True]), \
             patch.object(launcher.shutil, "which", return_value="cloudflared"), \
             patch.object(launcher, "alive", return_value=True), \
             patch.object(launcher, "tunnel_from_log", side_effect=[
                 "https://old.trycloudflare.com", "https://new.trycloudflare.com"
             ]), patch.object(launcher, "stop_owned_tunnel") as stop, \
             patch.object(launcher, "launch") as launch, \
             patch.object(launcher, "http_json", side_effect=[{"success": True}, {}]):
            with tempfile.TemporaryDirectory() as directory:
                with patch.object(launcher, "RUNTIME", Path(directory)):
                    endpoint = launcher.ensure_tunnel(8000, base, state)
        self.assertEqual(endpoint, "https://new.trycloudflare.com/webhook")
        stop.assert_called_once_with(state)
        launch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
