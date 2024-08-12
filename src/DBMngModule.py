# -*- coding: utf-8 -*-
# Определяем путь к корневой директории проекта
import os, sys
from datetime import datetime

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# Добавляем корневую директорию проекта в sys.path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import json
import sqlite3
import shutil
from getpass import getuser

def read_json(path_to_file):
    '''
    Считывает JSON файл из переданного пути
    и возвращает полученную информацию
    '''
    with open(path_to_file,'r', encoding='utf-8') as Json_file:
        templates = json.load(Json_file)
    return (templates)

class CADFolderDB():
    def __init__(self):
        path_to_config = os.path.dirname(os.path.abspath(__file__))+'\\config.json'
        config = read_json(path_to_config)
        self.root_dir = '\\'+config['PROJECT ROOT'][0]
        print(self.root_dir)

        self.db_path = project_root+'\\databases\\CADFolder.db'
        self.main_conn = sqlite3.connect(self.db_path)
        self.main_cursor = self.main_conn.cursor()
        print('Установлено соединение с главной базой данных')
        
    def update_project(self):
        self.main_cursor.execute('''
            CREATE TABLE IF NOT EXISTS file_structure (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            network_path TEXT,
            status TEXT,
            type TEXT,
            last_modified TEXT
            )
                ''')
        """
        Обходит директории и файлы в root_dir и сохраняет их структуру в базу данных.
        """
        # Проверка наличия записи перед вставкой
        # Создания exists_paths со списком всех путей
        self.main_cursor.execute('''
            SELECT network_path FROM file_structure
        ''')
        # Преобразование в множество для быстрого поиска
        exists_paths = set(
            row[0] for row in self.main_cursor.fetchall()) 

        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            # Сохранение директорий
            for dirname in dirnames:
                full_path = os.path.join(dirpath, dirname).replace("\\", "/")
                if full_path not in exists_paths:
                    self.main_cursor.execute('''
                        INSERT INTO file_structure 
                        (name, network_path, status, type, last_modified)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        dirname, 
                        full_path,
                        'Зарегистрирован', 
                        'directory', 
                        datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat()
                    ))
                else:
                    exists_paths.discard(full_path)

            # Сохранение файлов
            for filename in filenames:
                if not filename.startswith('~') and filename[-3:] not in ['bak']:
                    full_path = os.path.join(dirpath, filename).replace("\\", "/")
                    if full_path not in exists_paths:
                        self.main_cursor.execute('''
                            INSERT INTO file_structure 
                            (name, network_path, status, type, last_modified)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (
                            filename, 
                            full_path,
                            'Зарегистрирован', 
                            'file', 
                            datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat()
                        ))
                    else:
                        exists_paths.discard(full_path)  # Удаление из множества
        # если в полученном массиве из базы остались записи, т.е. файл был удален с диска
        # Удаление записей, которые больше не существуют на диске
        if exists_paths:
            for path in exists_paths:
                self.main_cursor.execute("""DELETE FROM file_structure 
                                         WHERE network_path = ?""", 
                                         (path,))

        self.main_conn.commit()
        self.main_conn.close()


    def sync_to_local(self):
        user_name = getuser()
        user_db = project_root + '\\databases\\CADFolder_{}.db'.format(user_name)
        local_root = os.path.join(os.getenv('USERPROFILE'), 'AppData', 'NerpaSyncVault', 'YKProject')

        # Создание или подключение пользовательской базы данных
        user_conn = sqlite3.connect(user_db)
        user_cursor = user_conn.cursor()
        print('Установлено подключение к локальной базе данных')
        user_cursor.execute('''
            CREATE TABLE IF NOT EXISTS file_structure (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            local_path TEXT,
            status TEXT,
            type TEXT,
            last_modified TEXT
            )
        ''')

        # Синхронизация директорий
        self.main_cursor.execute("SELECT network_path, last_modified FROM file_structure WHERE type='directory'")
        network_directories = self.main_cursor.fetchall()

        synced_local_paths = set()

        for network_path, last_modified in network_directories:
            local_directory_path = local_root + network_path.split('CAD', 1)[-1].replace('/', '\\')
            local_directory_name = os.path.basename(local_directory_path)

            # Проверка наличия записи перед вставкой
            user_cursor.execute('''
                SELECT 1 FROM file_structure WHERE name = ? AND local_path = ? AND type = 'directory'
            ''', (local_directory_name, local_directory_path))
            exists = user_cursor.fetchone()

            synced_local_paths.add(local_directory_path)

            if not exists:
                # Вставляем новую запись и создаем директорию в локальном хранилище
                user_cursor.execute('''
                    INSERT INTO file_structure 
                    (name, local_path, status, type, last_modified)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    local_directory_name, 
                    local_directory_path,
                    'Зарегистрирован', 
                    'directory', 
                    last_modified
                ))
                os.makedirs(local_directory_path, exist_ok=True)
                print('Создана папка по пути {}'.format(local_directory_path))
        
        # Синхронизация файлов
        self.main_cursor.execute("SELECT network_path, last_modified FROM file_structure WHERE type='file'")
        network_files = self.main_cursor.fetchall()

        for network_path, last_modified in network_files:
            local_file_path = local_root + network_path.split('CAD', 1)[-1].replace('/', '\\')
            local_file_name = os.path.basename(local_file_path)

            # Проверка наличия записи перед вставкой
            user_cursor.execute('''
                SELECT 1 FROM file_structure WHERE name = ? AND local_path = ? AND type = 'file'
            ''', (local_file_name, local_file_path))
            exists = user_cursor.fetchone()

            synced_local_paths.add(local_file_path)

            if not exists:
                local_file_dir = os.path.dirname(local_file_path)
                os.makedirs(local_file_dir, exist_ok=True)

                # Вставляем новую запись и копируем файл в локальное хранилище
                user_cursor.execute('''
                    INSERT INTO file_structure 
                    (name, local_path, status, type, last_modified)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    local_file_name, 
                    local_file_path,
                    'Зарегистрирован', 
                    'file', 
                    last_modified
                ))
                shutil.copy2(network_path, local_file_path)
                print('Попытка создать папку по пути {}, копирование файла {}'.format(local_file_dir, local_file_name))

        # Удаление файлов и папок, которых нет на сетевом диске
        user_cursor.execute("SELECT local_path FROM file_structure")
        local_paths = set(row[0] for row in user_cursor.fetchall())

        paths_to_delete = local_paths - synced_local_paths

        for path in paths_to_delete:
            if os.path.exists(path):
                if os.path.isfile(path):
                    os.remove(path)
                    print('Удален {}'.format(path))
                elif os.path.isdir(path):
                    shutil.rmtree(path)
                    print('Удален {}'.format(path))
                # Удалить запись из локальной базы данных
                user_cursor.execute("DELETE FROM file_structure WHERE local_path = ?", (path,))

        user_conn.commit()
        user_conn.close()
        self.main_conn.close()
           



    


