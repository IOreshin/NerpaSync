# -*- coding: utf-8 -*-

import os, sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Добавляем корневую директорию проекта в sys.path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from gui import NerpaSyncMain

if __name__ == '__main__':
    window = NerpaSyncMain()
