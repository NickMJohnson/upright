"""Warehouse inventory barcode-scanning toolkit.

Drone-agnostic perception pipeline (decode 1D/2D barcodes from imagery) plus a
client stub for pulling captured media from the Skydio Cloud API.
"""

from .detector import Detection, decode_frame, dedupe

__all__ = ["Detection", "decode_frame", "dedupe"]
__version__ = "0.1.0"
