from pydoover.docker import run_app

from .application import JcbLivelinkPlatformApplication
from .app_config import JcbLivelinkPlatformConfig

def main():
    """
    Run the application.
    """
    run_app(JcbLivelinkPlatformApplication(config=JcbLivelinkPlatformConfig()))
