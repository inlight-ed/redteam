import sys
sys.path.insert(0, '.')

try:
    from behaviors.scanner import ScannerAgent
    from behaviors.multi_tab import MultiTabAgent
    print("SUCCESS: Все импорты работают корректно!")
except ModuleNotFoundError as e:
    print(f"ERROR: {e}")
