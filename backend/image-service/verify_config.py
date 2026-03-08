#!/usr/bin/env python3
"""
Verify that the image-service can read configuration from the root .env file.

Usage: python3 verify_config.py
"""

from pathlib import Path
import sys

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("Configuration Verification")
print("=" * 70)
print()

# Check paths
from config.settings import _SERVICE_ROOT, _PROJECT_ROOT, _ROOT_ENV, _LOCAL_ENV, _ENV_FILE

print("📁 Path Information:")
print("-" * 70)
print(f"Service root:  {_SERVICE_ROOT}")
print(f"Project root:  {_PROJECT_ROOT}")
print(f"Root .env:     {_ROOT_ENV}")
print(f"Local .env:    {_LOCAL_ENV}")
print(f"Using .env:    {_ENV_FILE}")
print()

# Check if files exist
print("📄 File Status:")
print("-" * 70)
print(f"Root .env exists:  {'✅ YES' if _ROOT_ENV.exists() else '❌ NO'}")
print(f"Local .env exists: {'✅ YES' if _LOCAL_ENV.exists() else '❌ NO'}")
print()

# Load settings
from config.settings import settings

print("⚙️  Configuration Values:")
print("-" * 70)
print(f"USE_OPTIMIZED_PREPROCESSING: {settings.use_optimized_preprocessing}")
print(f"OPTIMIZED_TARGET_SIZE:       {settings.optimized_target_size}")
print(f"PROCESSING_MODE:             {settings.processing_mode}")
print(f"PARALLEL_WORKERS:            {settings.parallel_workers}")
print(f"BATCH_SIZE:                  {settings.batch_size}")
print(f"DEVICE:                      {settings.device}")
print(f"INPUT_FOLDER:                {settings.input_folder}")
print(f"OUTPUT_FOLDER:               {settings.output_folder}")
print(f"MONGODB_URI:                 {settings.mongodb_uri[:50]}...")
print(f"MONGODB_DB_NAME:             {settings.mongodb_db_name}")
print(f"LOG_LEVEL:                   {settings.log_level}")
print()

# Summary
print("=" * 70)
if _ROOT_ENV.exists() and _ENV_FILE == _ROOT_ENV:
    print("✅ SUCCESS: Using root .env file")
    print(f"   {_ROOT_ENV}")
    if settings.use_optimized_preprocessing:
        print("   Optimizations are ENABLED")
    else:
        print("   Optimizations are DISABLED (set USE_OPTIMIZED_PREPROCESSING=true)")
elif _LOCAL_ENV.exists() and _ENV_FILE == _LOCAL_ENV:
    print("⚠️  WARNING: Using local .env file")
    print(f"   {_LOCAL_ENV}")
    print("   Root .env not found, using local configuration")
else:
    print("❌ ERROR: No .env file found")
    print("   Create .env in project root or image-service directory")

print("=" * 70)
print()

# Performance configuration summary
if settings.use_optimized_preprocessing or settings.processing_mode != "sequential":
    print("🚀 Performance Optimizations Summary:")
    print("-" * 70)
    
    speedup = 1.0
    notes = []
    
    if settings.use_optimized_preprocessing:
        speedup *= 2.5
        notes.append(f"✅ Optimized preprocessing ({settings.optimized_target_size}px)")
    else:
        notes.append(f"⚪ Standard preprocessing ({settings.max_image_side_px}px)")
    
    if settings.processing_mode == "parallel":
        speedup *= 4.0
        notes.append(f"✅ Parallel processing ({settings.parallel_workers} workers)")
    elif settings.processing_mode == "batched":
        speedup *= 3.0
        notes.append(f"✅ Batched processing ({settings.parallel_workers} workers, batch={settings.batch_size})")
    elif settings.processing_mode == "streaming":
        speedup *= 2.5
        notes.append(f"✅ Streaming processing (chunk={settings.batch_size})")
    else:
        notes.append("⚪ Sequential processing")
    
    if settings.device in ("cuda", "mps"):
        speedup *= 2.0
        notes.append(f"✅ GPU acceleration ({settings.device.upper()})")
    else:
        notes.append("⚪ CPU processing")
    
    for note in notes:
        print(f"  {note}")
    
    print()
    print(f"Expected speedup: ~{speedup:.1f}x faster than baseline")
    
    if speedup >= 10:
        print("💨 MAXIMUM SPEED configuration!")
    elif speedup >= 5:
        print("🚀 HIGHLY OPTIMIZED configuration!")
    elif speedup >= 3:
        print("⚡ GOOD optimization level")
    else:
        print("💡 Consider enabling more optimizations")
    
    print("=" * 70)
    print()
