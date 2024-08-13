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

        self.db_path = project_root+'\\databases\\CADFolder.db'

    def update_project(self):
        # Создание нового соединения для каждого вызова
        conn = sqlite3.connect(self.db_path)
        print('Установлено соединение с базой данных CADFolder.db')
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS file_structure (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            network_path TEXT,
            status TEXT,
            type TEXT,
            last_modified TEXT
            )
        ''')

        # Создание множества всех существующих путей и их времени модификации
        exists_paths = {}
        cursor.execute('SELECT network_path, last_modified FROM file_structure')
        exists_paths = {row[0]: row[1] for row in cursor.fetchall()}

        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            for dirname in dirnames:
                full_path = os.path.join(dirpath, dirname).replace("\\", "/")
                last_modified = datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat()
                if full_path not in exists_paths:
                    cursor.execute('''
                        INSERT INTO file_structure 
                        (name, network_path, status, type, last_modified)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        dirname, 
                        full_path,
                        'Зарегистрирован', 
                        'directory', 
                        last_modified
                    ))
                elif exists_paths[full_path] != last_modified:
                    cursor.execute('''
                        UPDATE file_structure 
                        SET last_modified = ?
                        WHERE network_path = ?
                    ''', (
                        last_modified,
                        full_path
                    ))
                    print('Обновлена папка {}'.format(dirname))
                # Удаляем обработанный путь из exists_paths, так как он больше не требуется
                if full_path in exists_paths:
                    del exists_paths[full_path]

            for filename in filenames:
                if not filename.startswith('~') and filename[-3:] not in ['bak']:
                    full_path = os.path.join(dirpath, filename).replace("\\", "/")
                    last_modified = datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat()
                    if full_path not in exists_paths:
                        cursor.execute('''
                            INSERT INTO file_structure 
                            (name, network_path, status, type, last_modified)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (
                            filename, 
                            full_path,
                            'Зарегистрирован', 
                            'file', 
                            last_modified
                        ))
                    elif exists_paths[full_path] != last_modified:
                        cursor.execute('''
                            UPDATE file_structure 
                            SET last_modified = ?
                            WHERE network_path = ?
                        ''', (
                            last_modified,
                            full_path
                        ))
                        print('Обновлен файл {} в БД'.format(filename))
                    # Удаляем обработанный путь из exists_paths
                    if full_path in exists_paths:
                        del exists_paths[full_path]

        # Удаление записей, которые не были найдены в текущем обходе директории
        if exists_paths:
            for path in exists_paths:
                cursor.execute("""DELETE FROM file_structure WHERE network_path = ?""", (path,))

        conn.commit()
        conn.close()


    def check_for_changes(self):
        """
        Проверяет наличие изменений на сетевом диске и уведомляет пользователя.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT network_path, last_modified FROM file_structure')
        existing_files = cursor.fetchall()

        changed_files = []

        for path, last_modified in existing_files:
            if os.path.exists(path):
                if datetime.fromtimestamp(os.path.getmtime(path)).isoformat() != last_modified:
                    changed_files.append(path)
            else:
                changed_files.append(path)

        conn.close()
       
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

        #подключение к главной БД
        conn = sqlite3.connect(self.db_path)
        print('Установлено соединение с базой данных CADFolder.db')
        cursor = conn.cursor()

        # Синхронизация директорий
        cursor.execute("SELECT network_path, last_modified FROM file_structure WHERE type='directory'")
        network_directories = cursor.fetchall()

        synced_local_paths = set()

        for network_path, last_modified in network_directories:
            local_directory_path = local_root + network_path.split('CAD', 1)[-1].replace('/', '\\')
            local_directory_name = os.path.basename(local_directory_path)

            # Проверка наличия записи перед вставкой
            user_cursor.execute('''
                SELECT last_modified FROM file_structure WHERE name = ? AND local_path = ? AND type = 'directory'
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
            elif exists[0] != last_modified:
                # Обновляем запись, если last_modified отличается
                user_cursor.execute('''
                    UPDATE file_structure
                    SET last_modified = ?, status = 'Обновлено'
                    WHERE local_path = ? AND type = 'directory'
                ''', (last_modified, local_directory_path))
                print('Обновлена папка по пути {}'.format(local_directory_path))

        # Синхронизация файлов
        cursor.execute("SELECT network_path, last_modified FROM file_structure WHERE type='file'")
        network_files = cursor.fetchall()

        for network_path, last_modified in network_files:
            local_file_path = local_root + network_path.split('CAD', 1)[-1].replace('/', '\\')
            local_file_name = os.path.basename(local_file_path)

            # Проверка наличия записи перед вставкой или обновлением
            user_cursor.execute('''
                SELECT last_modified FROM file_structure WHERE name = ? AND local_path = ? AND type = 'file'
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
                print('Копирование файла {} в {}'.format(local_file_name, local_file_path))
            elif exists[0] != last_modified:
                # Обновляем файл и запись, если last_modified отличается
                shutil.copy2(network_path, local_file_path)
                user_cursor.execute('''
                    UPDATE file_structure
                    SET last_modified = ?, status = 'Обновлено'
                    WHERE local_path = ? AND type = 'file'
                ''', (last_modified, local_file_path))
                print('Обновлен файл {} в {}'.format(local_file_name, local_file_path))

        # Удаление файлов и папок, которых нет на сетевом диске
        user_cursor.execute("SELECT local_path FROM file_structure")
        local_paths = set(row[0] for row in user_cursor.fetchall())

        paths_to_delete = local_paths - synced_local_paths

        for path in paths_to_delete:
            if os.path.exists(path):
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                        print('Удален файл {}'.format(path))
                    elif os.path.isdir(path):
                        shutil.rmtree(path, ignore_errors=True)
                        print('Удалена директория {}'.format(path))

                    # Удалить запись из локальной базы данных только если удаление было успешным
                    user_cursor.execute("DELETE FROM file_structure WHERE local_path = ?", (path,))
                except Exception as e:
                    print("Ошибка при удалении {}: {}".format(path, e))

        user_conn.commit()
        user_conn.close()
        conn.close()

    def update_file_status(self, file_name, action):
        # Подключение к базе данных
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        print('Подключение к главной БД')

        # Поиск файла по имени
        cursor.execute("SELECT network_path FROM file_structure WHERE name = ?", (file_name,))
        result = cursor.fetchone()

        if result:
            file_path = result[0]

            if action == "unregister":
                # Обновление статуса в базе данных
                cursor.execute("UPDATE file_structure SET status = ? WHERE name = ?", (getuser(), file_name))
                # Установка атрибута "только для чтения" на сетевом диске
                os.chmod(file_path, 0o444)
                print("Файл {} разрегистрирован. На сетевом диске установлен статус только для чтения".format(file_name))

            elif action == "register":
                # Создание локального пути к файлу
                local_file_path = os.path.join(
                    os.getenv('USERPROFILE'),
                    'AppData',
                    'NerpaSyncVault',
                    'YKProject folder',
                )
                user_name = getuser()
                user_db = project_root + '\\databases\\CADFolder_{}.db'.format(user_name)
                local_root = os.path.join(os.getenv('USERPROFILE'), 'AppData', 'NerpaSyncVault', 'YKProject')

                # Создание или подключение пользовательской базы данных
                user_conn = sqlite3.connect(user_db)
                user_cursor = user_conn.cursor()
                print('Установлено подключение к локальной базе данных')
                user_cursor.execute("SELECT local_path FROM file_structure WHERE name = ?", (file_name,))
                local_file_path = user_cursor.fetchone()[0]
                # Нормализация пути для текущей ОС
                local_file_path = os.path.normpath(local_file_path)

                # Отладочная информация
                print("Попытка доступа к локальному файлу по пути: {}".format(local_file_path))

                if not os.path.exists(local_file_path):
                    print("Ошибка: Локальный файл {} не найден".format(local_file_path))
                    return

                # Снятие атрибута "только для чтения"
                os.chmod(file_path, 0o666)

                # Копирование файла с локального хранилища на сетевой диск с заменой
                shutil.copy2(local_file_path, file_path)

                # Обновление статуса в базе данных
                cursor.execute("UPDATE file_structure SET status = 'Зарегистрирован' WHERE name = ?", (file_name,))
                print("Файл {} зарегистрирован и скопирован на сетевой диск".format(file_name))

        conn.commit()
        conn.close()
        print('Соединение с главной ДБ завершено успешно')
           



    


