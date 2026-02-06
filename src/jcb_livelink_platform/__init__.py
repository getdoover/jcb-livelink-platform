from .application import JcbLivelinkPlatformProcessor


def handler(event, context):
    """Lambda handler entry point for JCB LiveLink Platform processor."""
    processor = JcbLivelinkPlatformProcessor(**event)
    processor.execute()
