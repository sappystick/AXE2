#!/usr/bin/env python3
"""Kept for old commands: the sign-off is now the smart runner at the repository root (run.py: ledger, failed-only reruns, routing fallbacks).
usage: python3 rf2/head/rf2_signoff.py [--cold]  ==  python3 run.py [--cold]"""
import os, sys, subprocess
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.exit(subprocess.run([sys.executable, os.path.join(ROOT, "run.py")] + sys.argv[1:], cwd=ROOT).returncode)
