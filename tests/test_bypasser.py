"""Offline tests for the missing-shadow-root regression."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


class Disconnected(Exception):
    pass


spec = importlib.util.spec_from_file_location(
    'bypasser_under_test', Path(__file__).resolve().parents[1] / 'cloudflyer/bypasser.py')
module = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {
    'DrissionPage': types.SimpleNamespace(ChromiumPage=object),
    'DrissionPage.items': types.SimpleNamespace(ChromiumElement=object),
    'DrissionPage.errors': types.SimpleNamespace(PageDisconnectedError=Disconnected),
}):
    spec.loader.exec_module(module)


class BypasserTests(unittest.TestCase):
    def driver_with_input(self):
        element = Mock()
        element.attrs = {'name': 'cf-turnstile-response', 'type': 'hidden'}
        driver = Mock()
        driver.eles.return_value = [element]
        return driver, element

    def test_missing_shadow_root_uses_recursive_fallback(self):
        driver, element = self.driver_with_input()
        element.parent.return_value.shadow_root = None
        bypasser = module.CloudflareBypasser(driver)
        iframe, button = Mock(), object()
        bypasser.search_recursively_shadow_root_with_iframe = Mock(return_value=iframe)
        bypasser.search_recursively_shadow_root_with_cf_input = Mock(return_value=button)
        self.assertIs(bypasser.locate_cf_button(), button)
        bypasser.search_recursively_shadow_root_with_iframe.assert_called_once_with(driver.ele.return_value)
        bypasser.search_recursively_shadow_root_with_cf_input.assert_called_once_with(iframe.return_value)

    def test_fast_path_still_returns_button(self):
        driver, element = self.driver_with_input()
        button = object()
        element.parent.return_value.shadow_root.child.return_value.return_value.shadow_root.return_value = button
        bypasser = module.CloudflareBypasser(driver)
        self.assertIs(bypasser.locate_cf_button(), button)
        driver.ele.assert_not_called()

    def test_disconnect_is_not_swallowed_as_missing_dom(self):
        driver, element = self.driver_with_input()
        element.parent.side_effect = Disconnected()
        bypasser = module.CloudflareBypasser(driver)
        with self.assertRaises(Disconnected):
            bypasser.click_verification_button()


if __name__ == '__main__':
    unittest.main()
