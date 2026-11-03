"""Checkout wrapper for the installed conversation candidate command."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from cpu_llm.conversation_candidates import SOURCES,prepare,prompts,main

if __name__=='__main__':main()
