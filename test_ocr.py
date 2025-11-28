#!/usr/bin/env python3
import sys

print("Testing OCR installations...\n")

# Test doctr
try:
    from doctr.models import ocr_predictor
    print("✓ python-doctr is installed and working")
    DOCTR_OK = True
except Exception as e:
    print(f"✗ python-doctr error: {e}")
    DOCTR_OK = False

# Test pytesseract
try:
    import pytesseract
    print("✓ pytesseract is installed")
    PYTESSERACT_OK = True
except Exception as e:
    print(f"✗ pytesseract error: {e}")
    PYTESSERACT_OK = False

# Test torch
try:
    import torch
    print(f"✓ PyTorch {torch.__version__} is installed")
except Exception as e:
    print(f"✗ PyTorch error: {e}")

print("\n" + "="*50)
if DOCTR_OK:
    print("✓ OCR is ready to use!")
elif PYTESSERACT_OK:
    print("⚠ Using pytesseract as OCR (install doctr for better results)")
else:
    print("✗ No OCR available. Install with:")
    print("  pip install python-doctr[torch]")
    print("  or")
    print("  pip install pytesseract")