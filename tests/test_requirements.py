import unittest
from unittest.mock import patch
from blocker import firewall


class RequirementsTests(unittest.TestCase):
    def test_only_active_profiles_are_required(self):
        result = {"currentProfiles": 3, "enabledProfiles": [
            {"profile": 1, "enabled": True},
            {"profile": 2, "enabled": False},
            {"profile": 4, "enabled": False}]}
        self.assertEqual(firewall.disabled_active_profiles(result), [2])

    def test_unknown_firewall_state_is_not_success(self):
        for result in ({}, None, {"currentProfiles": "4"},
                       {"currentProfiles": 2, "enabledProfiles": [{"profile": 2, "enabled": "false"}]},
                       {"currentProfiles": 2, "enabledProfiles": []}):
            with self.assertRaises(RuntimeError):
                firewall.disabled_active_profiles(result)

    def test_enable_requires_admin(self):
        with patch.object(firewall, "is_admin", return_value=False), patch.object(
            firewall, "powershell"
        ) as shell:
            with self.assertRaises(PermissionError):
                firewall.enable_firewall()
            shell.assert_not_called()

    def test_enable_rechecks_result(self):
        on = {"currentProfiles": 2, "enabledProfiles": [{"profile": 2, "enabled": True}]}
        off = {"currentProfiles": 2, "enabledProfiles": [{"profile": 2, "enabled": False}]}
        with patch.object(firewall, "is_admin", return_value=True), patch.object(
            firewall, "powershell"
        ), patch.object(firewall, "inspect_rules", return_value=on):
            self.assertEqual(firewall.enable_firewall(), on)
        with patch.object(firewall, "is_admin", return_value=True), patch.object(
            firewall, "powershell"
        ), patch.object(firewall, "inspect_rules", return_value=off):
            with self.assertRaises(RuntimeError):
                firewall.enable_firewall()
