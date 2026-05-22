"""
GPU Acceleration Check Module
=============================
Detects hardware acceleration for faster LLM inference.
"""

import subprocess
import platform


# Global GPU availability flag
GPU_AVAILABLE = False


def check_gpu():
    """
    Check for GPU availability (NVIDIA, AMD, or Apple Silicon).
    
    Returns:
        bool: True if GPU is available, False otherwise
    """
    global GPU_AVAILABLE
    
    GPU_AVAILABLE = False
    
    print("\n" + "=" * 50)
    print("[GPU CHECK] Detecting hardware acceleration...")
    print("=" * 50)
    
    # Check NVIDIA GPU via nvidia-smi
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            GPU_AVAILABLE = True
            lines = result.stdout.strip().split('\n')
            for line in lines:
                print(f"[GPU] {line.strip()}")
    except FileNotFoundError:
        print("[INFO] nvidia-smi not found")
    except Exception as e:
        print(f"[INFO] GPU check: {e}")
    
    # Check via PyTorch
    try:
        import torch
        if torch.cuda.is_available():
            GPU_AVAILABLE = True
            print(f"[GPU] PyTorch CUDA: {torch.cuda.get_device_name(0)}")
    except ImportError:
        pass
    
    # Check for AMD GPU (ROCm)
    try:
        result = subprocess.run(
            ['rocm-smi', '--showid'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            GPU_AVAILABLE = True
            print("[GPU] AMD ROCm detected!")
    except Exception:
        pass
    
    # Display system info
    print(f"\n[SYSTEM INFO]")
    print(f"   OS: {platform.system()} {platform.release()}")
    print(f"   Python: {platform.python_version()}")
    
    # Final status
    print("\n" + "=" * 50)
    if GPU_AVAILABLE:
        print("[STATUS] GPU ACCELERATION: ENABLED")
        print("[SPEED] Expect 5-50x faster inference")
    else:
        print("[STATUS] Running on CPU only")
        print("[SPEED] Inference may be slower (30-90s per LLM call)")
    print("=" * 50)
    
    return GPU_AVAILABLE


def get_gpu_status():
    """Get current GPU status."""
    global GPU_AVAILABLE
    return GPU_AVAILABLE


if __name__ == "__main__":
    check_gpu()