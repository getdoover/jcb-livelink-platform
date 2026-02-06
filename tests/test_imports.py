"""
Basic tests for an application.

This ensures all modules are importable and that the config is valid.
"""

def test_import_app():
    from jcb_livelink_platform.application import JcbLivelinkPlatformApplication
    assert JcbLivelinkPlatformApplication

def test_config():
    from jcb_livelink_platform.app_config import JcbLivelinkPlatformConfig

    config = JcbLivelinkPlatformConfig()
    assert isinstance(config.to_dict(), dict)

def test_ui():
    from jcb_livelink_platform.app_ui import JcbLivelinkPlatformUI
    assert JcbLivelinkPlatformUI

def test_state():
    from jcb_livelink_platform.app_state import JcbLivelinkPlatformState
    assert JcbLivelinkPlatformState