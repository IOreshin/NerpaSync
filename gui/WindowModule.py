# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk
import sys, os
import sqlite3
import shutil
from datetime import datetime
from getpass import getuser

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Добавляем корневую директорию проекта в sys.path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src import k3DMaker, CADFolderDB

class Window:
    '''
    Базовый класс для всех окон приложения
    '''
    def __init__(self):
        self.window_name = 'NerpaAI v2.0'
        
    def create_button(self, ttk, frame, text, command, width, state, row, column):
        '''
        Функция для создания кнопки
        '''
        button = ttk.Button(frame, text = text, command = command, 
                            width = width, state = state)
        button.grid(row = row, column = column, padx = 5, pady = 5)
        return button
    
    def get_center_window(self, root):
        '''
        Функция автоматического размещения окна по центру экрана
        '''
        s = root.geometry()
        s = s.split('+')
        s = s[0].split('x')
        w_root = int(s[0])
        h_root = int(s[1])

        w_screen = root.winfo_screenwidth()
        h_screen = root.winfo_screenheight()

        w = (w_screen - w_root) // 2
        h = (h_screen - h_root) // 2

        return w,h
    
class k3DMakerWindow:
    def __init__(self, root, doc_type, network_dir_path, local_dir_path, main_window_instance):
        self.root = root
        self.doc_type = doc_type
        self.network_dir_path = network_dir_path
        self.local_dir_path = local_dir_path
        self.main_window_instance = main_window_instance

        self.db_path = project_root+'\\databases\\CADFolder.db'

        self.get_ask_window()

    def get_ask_window(self):
        ask_window = tk.Toplevel(self.root)

        marking_label = ttk.Label(ask_window, text = 'Обозначение:')
        marking_label.grid(row=0, column=0,
                           padx=10, pady=10)
        
        name_label = ttk.Label(ask_window, text='Наименование:')
        name_label.grid(row=1, column=0,
                        padx=10, pady=10)
        
        self.marking_entry = ttk.Entry(ask_window)
        self.marking_entry.grid(row=0, column=1,
                           padx=10, pady=10)
        
        self.name_entry = ttk.Entry(ask_window)
        self.name_entry.grid(row=1,column=1,
                        padx=10, pady=10)
        
        submit_button = ttk.Button(ask_window,
                                   text='Создать',
                                   command=self.create_3D_doc)
        submit_button.grid(row=2,column=1,
                           padx=10, pady=10)
        
    def create_3D_doc(self):
        try:
            marking = self.marking_entry.get()
            name = self.name_entry.get()

            if all(value not in [None,''] for value in [marking, name]):
                #составление пути для сохранения на сетевом диске
                if self.doc_type == 4.0:
                    extension = '.m3d'
                else:
                    extension = '.a3d'
                file_name = ''.join([marking, extension])
                network_file_path = '/'.join([self.network_dir_path, 
                                            file_name])
                local_file_path = '/'.join([self.local_dir_path, file_name])
                
                if k3DMaker(network_file_path,self.doc_type,marking,name):
                    try:
                        shutil.copy2(network_file_path, self.local_dir_path)
                        last_modified = datetime.fromtimestamp(os.path.getmtime(network_file_path)).isoformat()
                        name = ''.join([marking, extension])
                        status = getuser()
                        self.user_db_path = project_root+'\\databases\\CADFolder_{}.db'.format(status)

                        with sqlite3.connect(self.db_path) as conn, sqlite3.connect(self.user_db_path) as user_conn:
                            user_cursor = user_conn.cursor()
                            cursor = conn.cursor()
                            cursor.execute('''INSERT INTO file_structure
                                        (name, network_path, status, type, last_modified)
                                        VALUES (?,?,?,?,?)''',
                                        (name, network_file_path, status, 'file', last_modified))
                            user_cursor.execute('''INSERT INTO file_structure
                                        (name, local_path, status, type, last_modified)
                                        VALUES (?,?,?,?,?)''',
                                        (name, local_file_path, status, 'file', last_modified))
                            user_conn.commit()
                            conn.commit()
                            self.main_window_instance.update_treeview()

                    except Exception as e:
                        print('Ошибка копирования файла: {}'.format(e))
                        
            else:
                print('Одно из полей пустое. Введите значения в оба поля')
        
        except Exception as e:
            print(e)
            return

class FolderMakerWindow:
    def __init__(self, root, dir_name):
        self.root = root
        self.dir_name = dir_name
        self.db_path = project_root+'\\databases\\CADFolder.db'
        username = getuser()
        self.user_db_path = project_root+'\\databases\\CADFolder_{}.db'.format(username)

        self.create_ask_window()

    def create_ask_window(self):
        ask_window = tk.Toplevel(self.root)

        common_label = ttk.Label(ask_window, text='Введите название папки')
        common_label.grid(row=0, column=0, padx=10, pady=10, columnspan=2)

        name_label = ttk.Label(ask_window, text = 'Название:')
        name_label.grid(row=1, column=0,
                           padx=10, pady=10)
          
        self.name_entry = ttk.Entry(ask_window)
        self.name_entry.grid(row=1, column=1,
                           padx=10, pady=10)
        
        submit_button = ttk.Button(ask_window,
                                   text='Создать',
                                   command=self.create_folder)
        submit_button.grid(row=2,column=1,
                           padx=10, pady=10)
        
    def create_folder(self):
        try:
            folder_name = self.name_entry.get()
            if folder_name in ['', None]:
                print('Введите название папки')
                return
            
            with sqlite3.connect(self.db_path) as conn, sqlite3.connect(self.user_db_path) as user_conn:
                user_cursor = user_conn.cursor()
                cursor = conn.cursor()

                cursor.execute('''SELECT network_path FROM file_structure
                               WHERE name = ? AND type = "directory"''',(self.dir_name,))
                network_source_path = cursor.fetchone()[0]

                user_cursor.execute('''SELECT local_path FROM file_structure
                               WHERE name = ? AND type = "directory"''',(self.dir_name,))
                local_source_path = user_cursor.fetchone()[0]

                local_dir_path = '\\'.join([local_source_path, folder_name])
                network_dir_path = '/'.join([network_source_path,folder_name])
                try:
                    os.makedirs(local_dir_path, exist_ok=True)
                    os.makedirs(network_dir_path, exist_ok=True)
                except Exception as e:
                    print(e)
                    return

                try:
                    last_modified = datetime.fromtimestamp(os.path.getmtime(network_dir_path)).isoformat()
                    cursor.execute('''INSERT INTO file_structure
                                   (name, network_path, status, type, last_modified)
                                   VALUES (?,?,?,?,?)''',
                                   (folder_name, network_dir_path,'Зарегистрирован', 'directory', last_modified))
                    user_cursor.execute('''INSERT INTO file_structure
                                   (name, local_path, status, type, last_modified)
                                   VALUES (?,?,?,?,?)''',
                                   (folder_name, local_dir_path,'Зарегистрирован', 'directory', last_modified))
                    conn.commit()
                    user_conn.commit()
                    print('Папка {} успешно создана'.format(folder_name))

                except Exception as e:
                    print(e)
                    
        except Exception as e:
            print(e)

