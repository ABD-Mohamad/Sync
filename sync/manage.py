# sync/manage.py
import os
import sys
from pathlib import Path

# Must be at module level — not inside if __name__ == '__main__'
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("Couldn't import Django.") from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()