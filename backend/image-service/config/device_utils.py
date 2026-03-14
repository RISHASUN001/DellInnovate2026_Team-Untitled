"""
Device detection utility for automatic GPU selection based on OS.

This module provides a smart device detection system that automatically
selects the best available hardware accelerator:
- Windows/Linux: CUDA (NVIDIA GPUs)
- macOS: MPS (Metal Performance Shaders - Apple Silicon)
- Fallback: CPU

Usage:
    from config.device_utils import get_device
    
    device = get_device()
    model = model.to(device)
"""

from __future__ import annotations

import logging
import platform

logger = logging.getLogger(__name__)


def get_device(prefer: str | None = None) -> str:
    """
    Detect and return the best available device for PyTorch.
    
    Args:
        prefer: Optional device preference ("cuda", "mps", "cpu").
                If specified and available, this device will be used.
                If not available, falls back to auto-detection.
    
    Returns:
        Device string: "cuda", "mps", or "cpu"
    
    Device selection logic:
        1. If prefer is specified and available, use it
        2. Otherwise, auto-detect based on OS:
           - Windows: Check for CUDA
           - macOS: Check for MPS (Apple Silicon)
           - Linux: Check for CUDA
        3. Fallback to CPU if no accelerator available
    """
    try:
        import torch  # noqa: PLC0415
    except ImportError:
        logger.warning("PyTorch not installed. Defaulting to 'cpu'.")
        return "cpu"
    
    # Get OS information
    system = platform.system()
    
    # If user has a preference, try to honor it
    if prefer:
        prefer = prefer.strip().lower()
        if prefer == "cuda" and torch.cuda.is_available():
            logger.info("Using preferred device: CUDA (GPU)")
            return "cuda"
        elif prefer == "mps" and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            logger.info("Using preferred device: MPS (Apple Silicon GPU)")
            return "mps"
        elif prefer == "cpu":
            logger.info("Using preferred device: CPU")
            return "cpu"
        else:
            logger.warning("Preferred device '%s' not available. Auto-detecting...", prefer)
    
    # Auto-detect based on OS and availability
    if system == "Darwin":  # macOS
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            logger.info("Detected macOS with MPS support. Using MPS (Apple Silicon GPU).")
            return "mps"
        else:
            logger.info("macOS detected but MPS not available. Using CPU.")
            return "cpu"
    
    elif system == "Windows":
        if torch.cuda.is_available():
            cuda_name = torch.cuda.get_device_name(0)
            logger.info("Detected Windows with CUDA support. Using CUDA GPU: %s", cuda_name)
            return "cuda"
        else:
            logger.info("Windows detected but CUDA not available. Using CPU.")
            return "cpu"
    
    elif system == "Linux":
        if torch.cuda.is_available():
            cuda_name = torch.cuda.get_device_name(0)
            logger.info("Detected Linux with CUDA support. Using CUDA GPU: %s", cuda_name)
            return "cuda"
        else:
            logger.info("Linux detected but CUDA not available. Using CPU.")
            return "cpu"
    
    else:
        logger.warning("Unknown OS '%s'. Defaulting to CPU.", system)
        return "cpu"


def get_torch_dtype(device: str):
    """
    Get the appropriate torch dtype based on device.
    
    Args:
        device: Device string ("cuda", "mps", or "cpu")
    
    Returns:
        torch.dtype: bfloat16 for CUDA, float32 for others
    """
    try:
        import torch  # noqa: PLC0415
    except ImportError:
        logger.warning("PyTorch not installed.")
        return None
    
    if device == "cuda":
        return torch.bfloat16
    else:
        return torch.float32


def get_device_info() -> dict[str, str | bool]:
    """
    Get detailed information about available devices.
    
    Returns:
        Dictionary with device availability information
    """
    try:
        import torch  # noqa: PLC0415
    except ImportError:
        return {
            "os": platform.system(),
            "torch_available": False,
            "cuda_available": False,
            "mps_available": False,
            "selected_device": "cpu",
        }
    
    info = {
        "os": platform.system(),
        "torch_available": True,
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "mps_available": hasattr(torch.backends, "mps") and torch.backends.mps.is_available(),
        "selected_device": get_device(),
    }
    
    if info["cuda_available"]:
        info["cuda_version"] = torch.version.cuda
        info["cuda_device_name"] = torch.cuda.get_device_name(0)
        info["cuda_device_count"] = torch.cuda.device_count()
    
    return info


# For convenience, get the device once at module load
# This can be overridden by calling get_device() explicitly
DEFAULT_DEVICE = get_device()
