import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from blocker.core import ROOT, Pop, PRESETS, parse_config, build_plan, atomic_json
from blocker import firewall


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads((ROOT / "assets/sdr-deadlock.json").read_text(encoding="utf-8-sig"))
        self.pops = parse_config(self.raw)

    def test_snapshot_has_deadlock_relays_and_excludes_server_only_pops(self):
        self.assertEqual(len(self.pops), 33)
        self.assertNotIn("hel", {p.code for p in self.pops})
        self.assertIn("hkg", {p.code for p in self.pops})

    def test_each_preset_protects_all_allowed_addresses(self):
        known = {p.code for p in self.pops}
        for key, (_, _, codes, _) in PRESETS.items():
            with self.subTest(key=key):
                allowed = codes & known
                self.assertTrue(allowed)
                plan = build_plan(self.pops, allowed)
                protected = {ip for p in self.pops if p.code in allowed for ip in p.ips}
                blocked = {ip for r in plan for ip in r["ips"]}
                self.assertTrue(blocked)
                self.assertFalse(protected & blocked)
                self.assertEqual({r["code"] for r in plan}, known - allowed)

    def test_no_empty_or_unknown_allow_list(self):
        for allowed in [set(), {"unknown"}]:
            with self.assertRaises(ValueError):
                build_plan(self.pops, allowed)

    def test_allow_all_removes_restrictions(self):
        self.assertEqual(build_plan(self.pops, {p.code for p in self.pops}), [])

    def test_shared_ip_never_blocked(self):
        pops = [Pop("a", "A", ("8.8.8.8",), ""),
                Pop("b", "B", ("8.8.8.8", "1.1.1.1"), "")]
        self.assertEqual(build_plan(pops, {"a"}), [{"code": "b", "ips": ["1.1.1.1"]}])

    def test_reject_bad_configs(self):
        for data in [{}, {"revision": 1, "pops": {}},
                     {"revision": 1, "pops": {"bad;cmd": {}}},
                     {"revision": 1, "pops": {"x": {"relays": [{"ipv4": "127.0.0.1"}]}}}]:
            with self.assertRaises(ValueError):
                parse_config(data)

    def test_malformed_config_structures_raise_value_error(self):
        for raw in [None, [], "bad", {"revision": "bad", "pops": {}},
                    {"revision": True, "pops": {}},
                    {"revision": 10**30, "pops": {}},
                    {"revision": 1, "pops": {"x": None}},
                    {"revision": 1, "pops": {"x": {"relays": None}}},
                    {"revision": 1, "pops": {"x": {"relays": [None]}}},
                    {"revision": 1, "pops": {"x": {"relays": [{"ipv4": []}, {"ipv4": {"bad": 1}}]}}}]:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_config(raw)

    def test_persistence_unicode(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "settings.json"
            atomic_json(path, {"пресет": ["sto"]})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"пресет": ["sto"]})

    def test_no_firewall_write_without_admin(self):
        with patch.object(firewall, "is_admin", return_value=False), patch.object(firewall, "powershell") as ps:
            with self.assertRaises(PermissionError):
                firewall.apply_rules([], "fake.exe")
            with self.assertRaises(PermissionError):
                firewall.remove_rules()
            ps.assert_not_called()

    def test_only_valid_game_can_be_targeted(self):
        with patch.object(firewall, "is_admin", return_value=True), patch.object(firewall, "powershell") as ps:
            with self.assertRaises(ValueError):
                firewall.apply_rules([], "missing/deadlock.exe")
            ps.assert_not_called()

    def test_remove_only_owned_group(self):
        with patch.object(firewall, "is_admin", return_value=True), patch.object(firewall, "powershell", return_value={}) as ps:
            firewall.remove_rules()
            script = ps.call_args.args[0]
            self.assertIn("$_.Grouping -eq 'DeadlockRelay.Managed.v1'", script)
            self.assertNotIn("advfirewall reset", script)

    def test_apply_script_scope_and_rollback(self):
        with tempfile.TemporaryDirectory() as temp:
            game = Path(temp) / "deadlock.exe"
            game.touch()
            with patch.object(firewall, "is_admin", return_value=True), patch.object(firewall, "powershell", return_value={}) as ps:
                firewall.apply_rules([{"code": "sto", "ips": ["8.8.8.8"]}], str(game))
                script = ps.call_args.args[0]
                self.assertIn("$r.ApplicationName = $data.program", script)
                self.assertIn("$r.Direction = 2; $r.Action = 0", script)
                self.assertLess(script.index("$p.Rules.Add($r)"), script.index("foreach ($r in $old)"))
                self.assertIn("foreach ($r in $removed)", script)
                self.assertIn("foreach ($name in $created)", script)


if __name__ == "__main__":
    unittest.main()
