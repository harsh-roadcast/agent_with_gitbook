"""Environment configuration for CPU-only processing to prevent MPS/GPU issues."""
import os

# Set environment variables BEFORE importing any ML libraries
# This prevents MPS/GPU memory issues and forces CPU-only processing
os.environ["PYTORCH_MPS_HIGH_WATERMARK_RATIO"] = "0.0"
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["MPS_ENABLE"] = "0"
os.environ["PYTORCH_MPS_ALLOCATOR"] = "garbage_collection"
os.environ["OMP_NUM_THREADS"] = "1"  # Limit OpenMP threads
os.environ["TOKENIZERS_PARALLELISM"] = "false"  # Prevent tokenizer warnings

# Force CPU device for PyTorch (will be applied when torch is imported)
os.environ["PYTORCH_DEVICE"] = "cpu"

print("✅ Environment configured for CPU-only processing")
