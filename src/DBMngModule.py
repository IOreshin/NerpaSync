# -*- coding: utf-8 -*-
# Определяем путь к корневой директории проекта
import os, sys, stat
from datetime import datetime

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# Добавляем корневую директорию проекта в sys.path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import sqlite3
import shutil
from getpass import getuser

from .KompasUtility import SetStatusDoc

from tkinter import filedialog


class CADFolderDB():
    def __init__(self):
        self.db_path = project_root+'\\databases\\CADFolder.db'
        self.username = getuser()

    def init_user_track(self):
        '''
        Метод создает таблицу в главной БД,
        в которую записывается имя пользователя,
        который последний внес изменения в БД
        '''
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS
                           user_tracking(
                           id INTEGER PRIMARY KEY AUTOINCREMENT,
                           last_user TEXT)''')
            cursor.execute('''INSERT INTO user_tracking (last_user)
                           VALUES (?)''', (self.username,))
            conn.commit()

    def update_last_user(self):
        '''
        Метод по обновлению последнего пользователя,
        вносившего изменения в БД
        '''
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE user_tracking
                SET last_user = ?
                WHERE id = 1
            ''', (self.username,))
            conn.commit()

    def get_last_user(self):
        '''
        Метод получения имени последнего пользователя,
        вносившего изменения в БД
        '''
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''SELECT last_user FROM user_tracking''')
            return cursor.fetchone()[0]

    def update_project(self):
        '''
        Метод по ручному принудительному обновлению или созданию
        проекта. Вызывает файловый диалог с выбором директории.
        После этого создается таблица(если надо) и заносятся или
        обновляются записи в таблице
        '''

        project_path = filedialog.askdirectory()
        if not project_path:
            print('Путь к проекту не выбран')
            return
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            print('Подключение к главной БД')
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
            # Получение существующих путей
            cursor.execute('SELECT network_path, last_modified FROM file_structure')
            exists_paths = {row[0]: row[1] for row in cursor.fetchall()}

            #последовательной обход директорий и файлов в главной папке проекта
            for dirpath, dirnames, filenames in os.walk(project_path):
                for dirname in dirnames:
                    full_path = os.path.join(dirpath, dirname).replace("\\", "/")
                    last_modified = datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat()
                    #если пути папки нет в БД
                    if full_path not in exists_paths:
                        cursor.execute('''
                            INSERT INTO file_structure 
                            (name, network_path, status, type, last_modified)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (dirname, full_path, 'Зарегистрирован', 'directory', last_modified))
                    #если запись есть, но она старая
                    elif exists_paths[full_path] != last_modified:
                        cursor.execute('''
                            UPDATE file_structure 
                            SET last_modified = ?
                            WHERE network_path = ?
                        ''', (last_modified, full_path))
                    #Случай, в котором папка существует и она корректно обновлена
                    exists_paths.pop(full_path, None)
                    self.set_read_only(full_path)

                for filename in filenames:
                    #исключения из перебора TEMP файлов(начинаются с ~) и BACKUP файлов КОМПАС
                    if not filename.startswith('~') and filename[-3:] not in ['bak']:
                        full_path = os.path.join(dirpath, filename).replace("\\", "/")
                        last_modified = datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat()
                        #если пути нет в БД
                        if full_path not in exists_paths:
                            cursor.execute('''
                                INSERT INTO file_structure 
                                (name, network_path, status, type, last_modified)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (filename, full_path, 'Зарегистрирован', 'file', last_modified))
                        #если путь есть, но дата изменения не актуальна
                        elif exists_paths[full_path] != last_modified:
                            cursor.execute('''
                                UPDATE file_structure 
                                SET last_modified = ?
                                WHERE network_path = ?
                            ''', (last_modified, full_path))
                        #Случай, в котором папка существует и она корректно обновлена
                        exists_paths.pop(full_path, None)
                        self.set_read_only(full_path)
            # Удаление несуществующих путей
            if exists_paths:
                cursor.executemany("DELETE FROM file_structure WHERE network_path = ?", 
                                   [(path,) for path in exists_paths])
            conn.commit()
            print('База данных обновлена')
        #создание и обновление таблицы с информацией о последнем пользователе
        self.init_user_track()
        self.update_last_user()

    def set_read_only(self, file_path):
        '''
        Метод для установки режима "Только для чтения"
        '''
        try:
            os.chmod(file_path, stat.S_IREAD)
        except Exception as e:
            print("Ошибка при установке атрибута 'только для чтения' для {}: {}".format(file_path,e))

    def sync_to_local(self):
        '''
        Метод для синхронизации данных с сетевого диска на локальный.
        Работает как на полный перенос, так и на обновление в соответсвии с данными в главной БД
        '''
        #инициализация пользовательских параметров
        user_name = getuser()
        user_db = project_root + '\\databases\\CADFolder_{}.db'.format(user_name)
        local_root = os.path.join(os.getenv('USERPROFILE'), 'AppData', 'NerpaSyncVault', 'YKProject')

        try:
            with sqlite3.connect(user_db) as user_conn, sqlite3.connect(self.db_path) as conn:
                # user_cursor - управление БД пользователя, cursor - управление главной БД
                user_cursor = user_conn.cursor()
                cursor = conn.cursor()
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
                cursor.execute("SELECT network_path, last_modified FROM file_structure WHERE type='directory'")
                network_directories = cursor.fetchall()
                synced_local_paths = set()

                for network_path, last_modified in network_directories:
                    #создание локальных параметров названий файлов
                    # TODO надо сделать более независиый от CAD метод
                    local_directory_path = os.path.join(local_root, network_path.split('CAD', 1)[-1].replace('/', '\\'))
                    local_directory_name = os.path.basename(local_directory_path)

                    #проверка существования записи в пользовательской БД о файле
                    user_cursor.execute('''
                        SELECT last_modified FROM file_structure WHERE name = ? AND local_path = ? AND type = 'directory'
                    ''', (local_directory_name, local_directory_path))
                    exists = user_cursor.fetchone()

                    synced_local_paths.add(local_directory_path)

                    if not exists:
                        user_cursor.execute('''
                            INSERT INTO file_structure 
                            (name, local_path, status, type, last_modified)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (local_directory_name, local_directory_path, 'Зарегистрирован', 'directory', last_modified))
                        os.makedirs(local_directory_path, exist_ok=True)
                        print('Создана папка по пути {}'.format(local_directory_path))
                    elif exists[0] != last_modified:
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
                    #создание локальных параметров названий файлов
                    # TODO надо сделать более независиый от CAD метод
                    local_file_path = os.path.join(local_root, 
                                                   network_path.split('CAD', 1)[-1].replace('/', '\\'))
                    local_file_name = os.path.basename(local_file_path)

                    user_cursor.execute('''
                        SELECT last_modified FROM file_structure WHERE name = ? AND local_path = ? AND type = 'file'
                    ''', (local_file_name, local_file_path))
                    exists = user_cursor.fetchone()

                    synced_local_paths.add(local_file_path)

                    if not exists:
                        local_file_dir = os.path.dirname(local_file_path)
                        os.makedirs(local_file_dir, exist_ok=True)
                        user_cursor.execute('''
                            INSERT INTO file_structure 
                            (name, local_path, status, type, last_modified)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (local_file_name, local_file_path, 'Зарегистрирован', 'file', last_modified))
                        shutil.copy2(network_path, local_file_path)
                        print('Копирование файла {} в {}'.format(local_file_name, local_file_path))
                        self.set_read_only(local_file_path)
                    elif exists[0] != last_modified:
                        #в случае, когда надо обновить файл сначала требуется снять режим "Только для чтения"
                        os.chmod(local_file_path, 0o666)
                        shutil.copy2(network_path, local_file_path)
                        user_cursor.execute('''
                            UPDATE file_structure
                            SET last_modified = ?, status = 'Обновлено'
                            WHERE local_path = ? AND type = 'file'
                        ''', (last_modified, local_file_path))
                        print('Обновлен файл {} в {}'.format(local_file_name, local_file_path))
                        self.set_read_only(local_file_path)

                # Удаление файлов и папок, которых нет на сетевом диске
                user_cursor.execute("SELECT local_path FROM file_structure")
                local_paths = set(row[0] for row in user_cursor.fetchall())

                paths_to_delete = local_paths - synced_local_paths

                for path in paths_to_delete:
                    if os.path.exists(path):
                        try:
                            if os.path.isfile(path):
                                os.chmod(path, 0o666)
                                os.remove(path)
                                print('Удален файл {}'.format(path))
                            elif os.path.isdir(path):
                                os.chmod(path, 0o666)
                                shutil.rmtree(path, ignore_errors=True)
                                print('Удалена папка {}'.format(path))
                            user_cursor.execute("DELETE FROM file_structure WHERE local_path = ?", (path,))
                        except Exception as e:
                            print("Ошибка при удалении {}: {}".format(path, e))

                user_conn.commit()
                print('Локальная синхронизация завершена.')

        except (sqlite3.Error, OSError) as e:
            print("Ошибка синхронизации с локальным хранилищем: {}".format(e))

    def update_file_status(self, file_name, action):
        '''
        Метод по установки статусов "Зарегистрировано" и "Разрегистрировано"
        '''
        # Подключение к главной базе данных
        try:
            user_name = getuser()
            user_db = project_root + '\\databases\\CADFolder_{}.db'.format(user_name)
            with sqlite3.connect(user_db) as user_conn, sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                user_cursor = user_conn.cursor()
                print('Подключение к главной и локальной БД')
                # Поиск файла по имени
                cursor.execute("SELECT network_path FROM file_structure WHERE name = ?", (file_name,))
                result = cursor.fetchone()
                if result:
                    network_file_path = result[0]
                    if action == "unregister":
                        # Обновление статуса в главной базе данных
                        cursor.execute("UPDATE file_structure SET status = ? WHERE name = ?", (getuser(), file_name))
                        #получение пути к файлу на локальном диске
                        user_cursor.execute("SELECT local_path FROM file_structure WHERE name = ?", (file_name,))
                        local_file_path = user_cursor.fetchone()[0]
                        local_file_path = os.path.normpath(local_file_path)
                        # Снятие атрибута "только для чтения" на локальном диске
                        os.chmod(local_file_path, 0o666)
                        SetStatusDoc(read_only=False, file_path=local_file_path)
                        print("Файл {} разрегистрирован".format(file_name))

                    elif action == "register":
                        # Создание локального пути к файлу
                        user_cursor.execute("SELECT local_path FROM file_structure WHERE name = ?", (file_name,))
                        local_file_path = user_cursor.fetchone()[0]
                        # Нормализация пути для текущей ОС
                        local_file_path = os.path.normpath(local_file_path)

                        # Отладочная информация
                        print("Попытка доступа к локальному файлу по пути: {}".format(local_file_path))

                        if not os.path.exists(local_file_path):
                            print("Ошибка: Локальный файл {} не найден".format(local_file_path))
                            return

                        # Снятие атрибута с локального файла "только для чтения"
                        os.chmod(network_file_path, 0o666)

                        # Копирование файла с локального хранилища на сетевой диск с заменой
                        shutil.copy2(local_file_path, network_file_path)

                        # Установка атрибута "только для чтения" для сетевого и локального файлов
                        self.set_read_only(network_file_path)
                        self.set_read_only(local_file_path)

                        SetStatusDoc(read_only=True, file_path = local_file_path)

                        # Обновление статуса в базе данных
                        last_modified = datetime.fromtimestamp(os.path.getmtime(network_file_path)).isoformat()
                        cursor.execute("UPDATE file_structure SET status = 'Зарегистрирован' WHERE name = ?", (file_name,))
                        cursor.execute("UPDATE file_structure SET last_modified = ? WHERE name = ?", (last_modified, file_name,))
                        print("Файл {} зарегистрирован и скопирован на сетевой диск".format(file_name))
        
                conn.commit()

        except (sqlite3.Error, OSError) as e:
            print("Ошибка синхронизации с локальным хранилищем: {}".format(e))
            


           



    


