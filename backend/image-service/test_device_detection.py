"""
Test script to verify GPU/device detection for the image service.

This script checks what device will be used for model inference and
provides detailed information about available accelerators.

Usage:
    python test_device_detection.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add parent directory to path to import from config
sys.path.insert(0, str(Path(__file__).parent))

from config.device_utils import get_device, get_device_info, get_torch_dtype


def print_separator(char: str = "=", length: int = 70) -> None:
    """Print a separator line."""
    print(char * length)


def main() -> None:
    """Run device detection tests and display results."""
    print_separator()
    print("🔍 Image Service - Device Detection Test")
    print_separator()
    print()
    
    # Get device info
    print("📊 System Information:")
    print_separator("-")
    
    info = get_device_info()
    for key, value in info.items():
        print(f"  {key:20s}: {value}")
    
    print()
    print_separator("-")
    print()
    
    # Test device detection
    print("🎯 Device Detection Results:")
    print_separator("-")
    
    device = get_device()
    print(f"  Selected Device: {device.upper()}")
    
    dtype = get_torch_dtype(device)
    if dtype:
        print(f"  Torch Data Type: {dtype}")
    
    print()
    
    # Provide recommendations
    print("💡 Recommendations:")
    print_separator("-")
    
    if device == "cuda":
        print("  ✅ CUDA GPU detected! Models will run on NVIDIA GPU.")
        print("  ⚡ Expected performance: Fast inference")
    elif device == "mps":
        print("  ✅ MPS (Apple Silicon) detected! Models will run on Apple GPU.")
        print("  ⚡ Expected performance: Fast inference on Apple Silicon")
    else:
        print("  ℹ️  Running on CPU. Consider using a GPU for faster inference:")
        print("     - Windows/Linux: Install CUDA-enabled PyTorch")
        print("     - macOS: Use Apple Silicon Mac with MPS support")
        print("  ⚠️  Expected performance: Slow inference")
    
    print()
    print_separator()
    print("✅ Device detection test complete!")
    print_separator()


if __name__ == "__main__":
    main()
