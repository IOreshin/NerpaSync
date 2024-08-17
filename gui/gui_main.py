# -*- coding: utf-8 -*-

import os
import sys
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

import queue

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Добавляем корневую директорию проекта в sys.path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from gui import gui_window
from src.DBMngModule import CADFolderDB
from src.KompasEventsHandler import KompasFrameHandler
from getpass import getuser

class RedirectText:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, message):
        # Добавляем текст в виджет и прокручиваем вниз
        self.text_widget.insert(tk.END, message)
        self.text_widget.yview(tk.END)

    def flush(self):
        # Необходимо для совместимости с файловым интерфейсом
        pass

class NerpaSyncMain(gui_window.Window):
    def __init__(self) -> None:
        super().__init__()
        self.main_root = tk.Tk()
        self.main_root.title('TkPDM')
        self.main_root.resizable(False, False)
        self.db_path = project_root+'\\databases\\CADFolder.db'
        self.last_modified_time = os.path.getmtime(self.db_path)
        
        self.kompas_handler_running = True  # Флаг для управления потоком

        self.user_name = getuser()  # Получаем имя текущего пользователя
        
        #инициализация UI
        self.init_frames()
        self.init_buttons()
        self.create_tree_view()

        try:
            self.cad_db = CADFolderDB()
            self.update_treeview()
        except:
            pass

        # Перенаправляем стандартный вывод в текстовый виджет
        #self.redirect_stdout()

        self.main_root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.event_queue = queue.Queue()

        # Инициализация и запуск обработчика событий Kompas в отдельном потоке
        self.kompas_handler = KompasFrameHandler(self.event_queue)
        self.kompas_handler.start()

        # Запуск проверки очереди событий
        self.main_root.after(10, self.check_event_queue)
        # Запуск периодической проверки изменений в БД
        self.main_root.after(1000, self.check_db_changes)
        
        self.main_root.mainloop()

    def check_db_changes(self):
        try:
            current_modified_time = os.path.getmtime(self.db_path)
            if current_modified_time != self.last_modified_time:
                print("База данных была изменена.")
                self.last_modified_time = current_modified_time
                self.on_database_change()

        except Exception as e:
            print("Ошибка при проверке изменений в БД: {}".format(e))

        # Повторяем проверку через 1 секунду (1000 мс)
        self.main_root.after(1000, self.check_db_changes)

    def on_database_change(self):
        # Здесь вызывается функция, которую нужно выполнить при изменении БД
        self.cad_db.sync_to_local()
        # Например, вы можете обновить TreeView:
        self.update_treeview()

    def check_event_queue(self):
        while not self.event_queue.empty():
            message = self.event_queue.get_nowait()
            # Обрабатываем сообщения о документах
            if isinstance(message, str):
                doc_name = message
                self.handle_document_status(doc_name)

        self.main_root.after(100, self.check_event_queue)


    def handle_document_status(self, doc_name):
        # Проверка наличия документа в TreeView
        for item in self.tree.get_children():
            node = self._find_node_by_text(item, doc_name)
            if node:
                item_values = self.tree.item(node, "values")
                status = item_values[0] if item_values else ""
                if status == "Зарегистрирован":
                    response = messagebox.askyesno(
                        "Разрегистрация документа",
                        "Документ '{}' зарегистрирован. Хотите разрегистрировать его?".format(doc_name)
                    )
                    if response:
                        self.cad_db.update_file_status(doc_name, "unregister")
                        self.update_treeview()
                break

            
    def _find_node_by_text(self, item, text):
        """
        Рекурсивно находит узел по тексту.
        """
        if self.tree.item(item, 'text') == text:
            return item
        for child in self.tree.get_children(item):
            result = self._find_node_by_text(child, text)
            if result:
                return result
        return None

    def init_frames(self):
        self.frames = {
            'admin': ttk.LabelFrame(self.main_root, borderwidth=5, relief='solid', text='Администрирование'),
            'treeview': ttk.LabelFrame(self.main_root, borderwidth=5, relief='solid', text='Дерево проекта'),
            'manager': ttk.LabelFrame(self.main_root, borderwidth=5, relief='solid', text='Управление файлами'),
            'file_maker': ttk.LabelFrame(self.main_root, borderwidth=5, relief='solid', text='Создание новых файлов'),
            'logs': ttk.LabelFrame(self.main_root, borderwidth=5, relief='solid', text='Логирование'),
        }

        self.frames['admin'].grid(row=0, column=0, padx=5, pady=5)
        self.frames['treeview'].grid(row=0, column=1, padx=5, pady=5, rowspan=2)
        self.frames['manager'].grid(row=1, column=0, padx=5, pady=5)
        self.frames['file_maker'].grid(row=2, column=0, padx=5, pady=5)
        self.frames['logs'].grid(row=2, column=1, padx=5, pady=5)

        # Создание текстового виджета для логирования
        self.log_text = scrolledtext.ScrolledText(self.frames['logs'], wrap=tk.WORD, height=8)
        self.log_text.grid(row=0, column=0, sticky='nsew')


    def redirect_stdout(self):
        # Перенаправляем вывод print в текстовый виджет
        sys.stdout = RedirectText(self.log_text)

    def create_tree_view(self):
        self.tree = ttk.Treeview(self.frames['treeview'])
        self.tree.pack(expand=True, fill='both')
        self.tree['columns'] = ('Status', 'Last Modified')
        self.tree.column('#0', width=400)
        self.tree.column('Status', width=150)
        self.tree.column('Last Modified', width=150)

        self.tree.heading('#0', text='Name')
        self.tree.heading('Status', text='Status')
        self.tree.heading('Last Modified', text='Last Modified')

        # Привязываем событие на изменение выделения в TreeView
        self.tree.bind("<<TreeviewSelect>>", self.on_treeview_select)

    def get_data_to_tree(self):
        conn = sqlite3.connect(os.path.join(project_root, 'databases', 'CADFolder.db'))
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
            Добавляет элементы в TreeView, если путь содержит папку 'CAD',
            и добавляет только те элементы, которые следуют за этой папкой.
        """
        tree_items = {}

        for item in data:
            name, network_path, status, item_type, last_modified = item
            path_parts = network_path.split('/')

            # Проверяем, есть ли в пути папка с "CAD" в названии
            cad_folder_found = False
            for index, part in enumerate(path_parts):
                if 'CAD' in part:
                    cad_folder_found = True
                    cad_index = index
                    break

            if not cad_folder_found:
                continue

            # Если папка с "CAD" является последней в пути, пропускаем этот элемент
            if cad_index == len(path_parts) - 1:
                continue

            # Начинаем добавлять элементы после папки с "CAD"
            parent = ''
            for i, part in enumerate(path_parts[cad_index + 1:], start=cad_index + 1):
                current_path = '/'.join(path_parts[:i + 1])

                if current_path not in tree_items:
                    parent_id = tree_items.get(parent, '')
                    if i == len(path_parts) - 1:
                        # Добавляем файл или папку, которая идет после "CAD"
                        if item_type == "directory":
                            tree_id = self.tree.insert(parent_id, 'end', text=part)
                        else:
                            tree_id = self.tree.insert(parent_id, 'end', text=part, values=(status, last_modified))
                    else:
                        # Добавляем промежуточные директории
                        tree_id = self.tree.insert(parent_id, 'end', text=part)
                    tree_items[current_path] = tree_id
                parent = current_path

    def update_treeview(self):
        """
        Обновляет содержимое Treeview, очищая его и заполняя заново.
        """
        # Сохранение состояния открытых узлов
        open_nodes = {}

        def save_state(node):
            item = self.tree.item(node)
            # Сохраняем состояние узла по тексту
            if 'text' in item:
                open_nodes[item['text']] = item['open']
            for child in self.tree.get_children(node):
                save_state(child)

        # Сохраняем состояние корневых узлов
        for node in self.tree.get_children():
            save_state(node)

        # Очистка Treeview
        self.tree.delete(*self.tree.get_children())

        # Получение данных и заполнение Treeview
        tree_data = self.get_data_to_tree()
        self.populate_treeview(tree_data)

        # Восстановление состояния узлов
        def restore_state():
            for text, should_open in open_nodes.items():
                node = self.find_node_by_text(text)
                if node:
                    self.tree.item(node, open=should_open)
                
        restore_state()

    def find_node_by_text(self, text):
        """
        Находит узел по тексту в Treeview.
        """
        def search_nodes(node):
            item = self.tree.item(node)
            if 'text' in item and item['text'] == text:
                return node
            for child in self.tree.get_children(node):
                result = search_nodes(child)
                if result:
                    return result
            return None
        # Проверяем корневые узлы
        for node in self.tree.get_children():
            result = search_nodes(node)
            if result:
                return result
        return None

    def sync_network_to_local(self):
        self.cad_db.sync_to_local()
        self.update_treeview()

    def update_cad_folder(self):
        self.cad_db.update_project()
        self.update_treeview()

    def unregister_file(self):
        selected_item = self.tree.selection()
        if selected_item:
            file_name = self.tree.item(selected_item)["text"]
            self.cad_db.update_file_status(file_name, "unregister")
            self.update_treeview()

    def register_file(self):
        selected_item = self.tree.selection()
        if selected_item:
            file_name = self.tree.item(selected_item)["text"]
            self.cad_db.update_file_status(file_name, "register")
            self.update_treeview()

    def on_treeview_select(self, event):
        self.update_buttons_state()

    def update_buttons_state(self):
        selected_item = self.tree.selection()

        # Деактивируем кнопки по умолчанию
        self.register_button.state(['disabled'])
        self.unregister_button.state(['disabled'])

        if selected_item:
            item_values = self.tree.item(selected_item, "values")
            status = item_values[0] if item_values else ""
            # Активируем кнопки в зависимости от условий
            if status == "Зарегистрирован":
                self.unregister_button.state(['!disabled'])
            elif status != "Зарегистрирован" and status == self.user_name:
                self.register_button.state(['!disabled'])

    def do_nothing(self):
        pass

    def init_buttons(self):
        button_config = [
            {'text': 'Обновить или создать проект', 'frame': 'admin',
             'command': self.update_cad_folder, 'state': 'normal', 'row': 0, 'col': 0},
            {'text': 'Синхронизовать с сетевого диска', 'frame': 'manager',
             'command': self.sync_network_to_local, 'state': 'normal', 'row': 1, 'col': 0},
             {'text': 'Разрегистрировать файл', 'frame': 'manager',
             'command': self.unregister_file, 'state': 'normal', 'row': 2, 'col': 0},
             {'text': 'Зарегистрировать файл', 'frame': 'manager',
             'command': self.register_file, 'state': 'normal', 'row': 3, 'col': 0},
             {'text': 'Открыть файл', 'frame': 'manager',
             'command': self.do_nothing, 'state': 'normal', 'row': 4, 'col': 0},
             {'text': 'Создать сборку', 'frame': 'file_maker',
             'command': self.do_nothing, 'state': 'normal', 'row': 0, 'col': 0},
             {'text': 'Создать деталь', 'frame': 'file_maker',
             'command': self.do_nothing, 'state': 'normal', 'row': 1, 'col': 0},
             {'text': 'Создать чертеж', 'frame': 'file_maker',
             'command': self.do_nothing, 'state': 'normal', 'row': 2, 'col': 0},
        ]

        buttons = []
        for config in button_config:
            frame = self.frames[config['frame']]
            row = config['row']
            col = config['col']
            button = self.create_button(ttk,
                                        frame,
                                        config['text'],
                                        config['command'],
                                        40,
                                        config['state'],
                                        row, col)
            buttons.append(button)
            if config['text'] == 'Зарегистрировать файл':
                self.register_button = button
            elif config['text'] == 'Разрегистрировать файл':
                self.unregister_button = button

        return buttons

    def on_closing(self):
        """
        Обработка закрытия окна, завершение потока сканирования.
        """
        if messagebox.askokcancel("Выход", "Вы действительно хотите выйти?"):
            self.kompas_handler.stop()  # Завершаем цикл обработки сообщений
            self.main_root.destroy()

if __name__ == '__main__':
    window = NerpaSyncMain()
