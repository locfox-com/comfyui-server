"""
Worker Processor Modules
"""
from .base import BaseProcessor
from .face_swap import FaceSwapProcessor
from .upscale import UpscaleProcessor
from .remove_bg import RemoveBackgroundProcessor

__all__ = [
    'BaseProcessor',
    'FaceSwapProcessor',
    'UpscaleProcessor',
    'RemoveBackgroundProcessor',
]
