# tests/__init__.py
import sys
from pathlib import Path

# Автоматически добавляем app в путь при импорте tests
sys.path.append(str(Path(__file__).parent.parent))
