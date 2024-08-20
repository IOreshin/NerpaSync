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
                network_file_path = '/'.join([self.network_dir_path, 
                                            marking])+extension
                
                if k3DMaker(network_file_path,self.doc_type,marking,name):
                    shutil.copy2(network_file_path, self.local_dir_path)
                    last_modified = datetime.fromtimestamp(os.path.getmtime(network_file_path)).isoformat()
                    name = ''.join([marking, extension])
                    status = getuser()

                    with sqlite3.connect(self.db_path) as conn:
                        cursor = conn.cursor()
                        cursor.execute('''INSERT INTO file_structure
                                    (name, network_path, status, type, last_modified)
                                    VALUES (?,?,?,?,?)''',
                                    (name, network_file_path, status, 'file', last_modified))
                        conn.commit()

                        CADFolderDB().sync_to_local()
                        self.main_window_instance.update_treeview()
                        
            else:
                print('Одно из полей пустое. Введите значения в оба поля')
        
        except Exception as e:
            print(e)
            return


