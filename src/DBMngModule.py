# -*- coding: utf-8 -*-
# Определяем путь к корневой директории проекта
import os, sys
from datetime import datetime

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Добавляем корневую директорию проекта в sys.path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import sqlite3
import shutil
from getpass import getuser

class CADFolderDB():
    def __init__(self):
        self.db_path = project_root+'\\databases\\CADFolder.db'
        self.main_conn = sqlite3.connect(self.db_path)
        self.main_cursor = self.main_conn.cursor()
        
    def update_project(self, root_dir):
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

        for dirpath, dirnames, filenames in os.walk(root_dir):
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
        #Задание начальных параметров. 
        user_name = getuser()
        user_db = project_root+'\\databases\\CADFolder_{}.db'.format(user_name)
        local_root = 'C:\\Users\\{}\\AppData\\NerpaSyncVault\\YKProject'.format(user_name)

        #создание или подключение пользовательской дб
        user_conn = sqlite3.connect(user_db)
        user_cursor = user_conn.cursor()
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

        #блок для получения списка папок из главной бд
        #и занесения этих папок в NerpaSyncVault
        self.main_cursor.execute("""
                    SELECT network_path, last_modified FROM
                    file_structure WHERE type='directory' """)
        network_directories = self.main_cursor.fetchall()

        for network_path in network_directories:
            adding_flag = False
            local_directory_path = local_root
            network_path_parts = network_path[0].split('/')
            for part in network_path_parts:
                if 'CAD' in part:
                    adding_flag = True
                if adding_flag is True:
                    local_directory_path += '\\'+part
                
            local_directory_parts = local_directory_path.split('\\')
            local_directory_name = local_directory_parts[-1]
    
            # Проверка наличия записи перед вставкой
            user_cursor.execute('''
                SELECT 1 FROM file_structure WHERE name = ? AND local_path = ? AND type = 'directory'
            ''', (local_directory_name, local_directory_path))
            exists = user_cursor.fetchone()

            if not exists:
                # Если запись не найдена, вставляем новую запись
                # и создаем папку в Vault
                user_cursor.execute('''
                    INSERT INTO file_structure 
                    (name, local_path, status, type, last_modified)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    local_directory_name, 
                    local_directory_path,
                    'Зарегистрирован', 
                    'directory', 
                    network_path[1]
                ))
                os.makedirs(local_directory_path, exist_ok=True)
        
        #блок получения списка файлов для копирования
        self.main_cursor.execute("""
                    SELECT network_path, last_modified FROM
                    file_structure WHERE type='file'""")
        network_files = self.main_cursor.fetchall()

        for network_path in network_files:
            adding_flag = False
            local_file_path = local_root
            network_path_parts = network_path[0].split('/')
            for part in network_path_parts:
                if 'CAD' in part:
                    adding_flag = True
                if adding_flag is True:
                    local_file_path += '\\'+part
            
            local_file_path_parts = local_file_path.split('\\')
            local_file_name = local_file_path_parts[-1]

            # Проверка наличия записи перед вставкой
            user_cursor.execute('''
                SELECT 1 FROM file_structure WHERE name = ? AND local_path = ? AND type = 'file'
            ''', (local_file_name, local_file_path))
            exists = user_cursor.fetchone()
            if not exists:
                local_file_dist = '\\'.join(local_file_path_parts[:-1])
                # Если запись не найдена, вставляем новую запись
                # и копируем файл в Vault
                user_cursor.execute('''
                    INSERT INTO file_structure 
                    (name, local_path, status, type, last_modified)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    local_file_name, 
                    local_file_path,
                    'Зарегистрирован', 
                    'file', 
                    network_path[1]
                ))
                shutil.copy(network_path[0], local_file_dist)

        user_conn.commit()
        user_conn.close()
        self.main_conn.close()
           



    


