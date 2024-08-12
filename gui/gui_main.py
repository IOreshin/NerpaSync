# -*- coding: utf-8 -*-
import os, sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Добавляем корневую директорию проекта в sys.path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from gui import gui_window
from src import DBMngModule

import sqlite3
import tkinter as tk
from tkinter import ttk, filedialog

class NerpaSyncMain(gui_window.Window):
    def __init__(self) -> None:
        super().__init__()
        self.main_root = tk.Tk()
        self.main_root.title('TkPDM')

        self.init_frames()
        buttons = self.init_buttons()

        self.create_tree_view()

        tree_data = self.get_data_to_tree()
        self.populate_treeview(tree_data)

        self.main_root.mainloop()

    def init_frames(self):
        self.frames = {
            'manager': ttk.LabelFrame(self.main_root, borderwidth=5, relief='solid', text='Управление'),
            'treeview': ttk.LabelFrame(self.main_root, borderwidth=5, relief='solid', text='Дерево проекта')
        }

        self.frames['manager'].grid(row=0, column=0, padx=5, pady=5)
        self.frames['treeview'].grid(row=0, column=1, padx=5, pady=5)

    def create_tree_view(self):
        self.tree = ttk.Treeview(self.frames['treeview'])
        self.tree.pack(expand=True, fill='both')
        self.tree['columns'] = ('Status','Last Modified')
        self.tree.column('#0', width=400)
        self.tree.column('Status', width=150)
        self.tree.column('Last Modified', width=150)

        self.tree.heading('#0', text='Name')
        self.tree.heading('Status', text='Status')
        self.tree.heading('Last Modified', text='Last Modified')

    def get_data_to_tree(self):
        conn = sqlite3.connect(project_root+'\\databases\\CADFolder.db')
        cursor = conn.cursor()

        cursor.execute('''SELECT name,
                       network_path,
                       status,
                       type, 
                       last_modified 
                       FROM file_structure ORDER BY network_path''')
        
        tree_data = cursor.fetchall()
        conn.close()
        
        return tree_data

    def populate_treeview(self, data):
        """
        Рекурсивно добавляет элементы в Treeview на основе данных.
        """
        # Словарь для хранения идентификаторов узлов
        tree_items = {}

        for item in data:
            name, network_path, status, item_type, last_modified = item
            path_parts = network_path.split('/')

            parent = ''
            for i, part in enumerate(path_parts[2:], start=2):  # Пропуск первых двух частей (//WIN-I3RA71IKHRF/CAD folder)
                current_path = '/'.join(path_parts[:i+1])

                if current_path not in tree_items:
                    parent_id = tree_items.get(parent, '')
                    if i == len(path_parts) - 1:  # Последний элемент в пути
                        if item_type == "directory":
                            tree_id = self.tree.insert(parent_id, 'end', text=part, open=False)
                        else:  # Файл
                            self.tree.insert(parent_id, 'end', text=part, values=(status, last_modified))
                    else:  # Промежуточные элементы (все они будут директориями)
                        tree_id = self.tree.insert(parent_id, 'end', text=part, open=False)

                    tree_items[current_path] = tree_id

                parent = current_path

    def update_treeview(self):
        """
        Обновляет содержимое Treeview, очищая его и заполняя заново.
        """
        # Очистка текущего содержимого дерева
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Получение обновленных данных
        tree_data = self.get_data_to_tree()

        # Заново заполнение дерева
        self.populate_treeview(tree_data)

    def sync_network_to_local(self):
        cad_folder_db = DBMngModule.CADFolderDB()
        cad_folder_db.sync_to_local()
        self.update_treeview()

    def update_cad_folder(self):
        cad_folder_db = DBMngModule.CADFolderDB()
        cad_folder_db.update_project()
        self.update_treeview()

    def do_nothing(self):
        pass

    def init_buttons(self):
        button_config = [
            {'text': 'Обновить проект', 'frame': 'manager',
             'command': self.update_cad_folder, 'state': 'normal', 'row': 0, 'col': 0},
             {'text': 'Синхронизовать с сетевого диска', 'frame': 'manager',
             'command': self.sync_network_to_local, 'state': 'normal', 'row': 1, 'col': 0}
        ]

        buttons = []
        for config in button_config:
            frame = self.frames[config['frame']]
            row = config['row']
            col = config['col']
            buttons.append(self.create_button(ttk,
                                              frame,
                                              config['text'],
                                              config['command'],
                                              40,
                                              config['state'],
                                              row, col))
        return buttons

if __name__ == '__main__':
    window = NerpaSyncMain()


        