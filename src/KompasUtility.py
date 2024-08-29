# -*- coding: utf-8 -*-

import os, sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Добавляем корневую директорию проекта в sys.path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pythoncom
from win32com.client import Dispatch, gencache
from tkinter.messagebox import showinfo
from getpass import getuser
import shutil, sqlite3
from datetime import datetime
 
def get_path():
    '''
    Получить путь в текущую директорию
    '''
    return os.path.dirname(os.path.abspath(__file__))


class KompasAPI:
    '''
    Класс для подключения к КОМПАС-3D.
    При super() наследовании передает основные интефейсы:
    module - API компаса, app - экземпляр Application,
    const - константы Компаса
    '''
    def __init__(self):
        self.module = gencache.EnsureModule("{69AC2981-37C0-4379-84FD-5DD2F3C0A520}", 0, 1, 0)
        self.app = self.module.IApplication(Dispatch("Kompas.Application.7")._oleobj_.QueryInterface(self.module.IApplication.CLSID, 
                                                                                                     pythoncom.IID_IDispatch))
        self.const = gencache.EnsureModule("{2CAF168C-7961-4B90-9DA2-701419BEEFE3}", 0, 1, 0).constants
        self.const2D = gencache.EnsureModule("{75C9F5D0-B5B8-4526-8681-9903C567D2ED}", 0, 1, 0).constants
        if self.app.Visible is False:
            self.app.Visible = True
    
    def get_part_dispatch(self):
        '''
        Возвращает указатель на интерфейс iPart7
        для сборки
        '''
        iKompasDocument = self.app.ActiveDocument
        if iKompasDocument:
            iKompasDocument3D = self.module.IKompasDocument3D(iKompasDocument)
            return iKompasDocument3D.TopPart
        self.app.MessageBoxEx('Ошибка получения указателя iPart7',
                              'Ошибка', 64)
    
    def get_bodies_array(self):
        '''
        Возвращает list указателей тел из сборки.
        Внутри встроена проверка на включению тела в спецификацию
        и проверку зеркальности
        '''
        iPart7 = self.get_part_dispatch()
        bodies_array = self.module.IFeature7(iPart7).ResultBodies

        bodies_dispatches = []
        if bodies_array is not None:
            if isinstance(bodies_array, tuple):
                for body_dispatch in bodies_array:
                    body_object = KompasItem(body_dispatch)
                    if body_dispatch.CreateSpcObjects is True and body_object.is_patterned() is False:
                        bodies_dispatches.append(body_dispatch)
                return bodies_dispatches
            else:
                if bodies_array.CreateSpcObjects is True:
                    return [bodies_array]
                else:
                    return None
        else:
            self.app.MessageBoxEx('В активном документе нет тел',
                                  'Ошибка', 64)
            return
    
class KompasItem:
    '''
    Класс с удобными методами для обработки тел и компонентов.
    Для создания объекта этого класса нужно передать Dispatch тела или компонента.
    '''
    def __init__(self, dispatch):
        self.dispatch = dispatch
        self.pattern_words = ['Массив', 'Зеркальное']
        self.kAPI = KompasAPI() 
        self.module = self.kAPI.module
        self.app = self.kAPI.app

    def get_prp_value(self,ID): 
        '''
        Возвращает значение свойства по переданному ID. Формат ID - float
        '''
        iPropertyMng = self.module.IPropertyMng(self.app)
        iPropertyKeeper = self.module.IPropertyKeeper(self.dispatch)
        return iPropertyKeeper.GetPropertyValue(iPropertyMng.GetProperty(self.app.ActiveDocument, ID),'',True, True)[1]

    def set_prp_value(self,ID, PrpValue):
        '''
        Устанавливает значение свойства по переданному ID. Формат ID - float
        '''
        iPropertyMng = self.module.IPropertyMng(self.app)
        iPropertyKeeper = self.module.IPropertyKeeper(self.dispatch)
        set_prp = iPropertyKeeper.SetPropertyValue(iPropertyMng.GetProperty(self.app.ActiveDocument, ID), PrpValue, True)
        return set_prp

    def is_patterned(self): 
        '''
        Метод проверки получен объект массивом или нет
        '''
        try:
            sub_features = self.module.IFeature7(self.dispatch).SubFeatures(0, True, True)
            for sub in sub_features:
                return any(word in sub.Name for word in self.pattern_words)
        except:
            return False

class SetStatusDoc(KompasAPI):
    '''
    Класс для установки статуса документа, открытого в Компас
    Входные параметры:
    read_only - True - только для чтения, False - редактирование
    file_path - полный путь на локальном диске
    '''
    def __init__(self, read_only:bool, file_path:str):
        super().__init__()
        self.read_only = read_only
        self.file_path = file_path
        self.set_doc_status()

    def set_doc_status(self):
        iDocuments = self.app.Documents
        for i in range(iDocuments.Count):
            if iDocuments.Item(self.file_path):
                iKompasDocument = iDocuments.Item(self.file_path)
                iKompasDocument.ReadOnly = self.read_only
                break

class OpenDoc(KompasAPI):
    '''
    Класс для открытия документа Компас.
    Входные параметры:
    open_state - True - видимый режим, False - невидимый режим
    file_path - полный путь к файлу
    '''
    def __init__(self, open_state:bool,file_path:str):
        super().__init__()
        self.file_path = file_path
        self.open_state = open_state
        self.open_doc()

    def open_doc(self):
        iDocuments = self.app.Documents
        iDocuments.Open(self.file_path, True, self.open_state)

class k3DMaker(KompasAPI):
    '''
    Класс для создания 3D документов Компас
    Входные параметры:
    dir_path - путь в директорию на сетевом диске
    doc_type - тип документа. 4.0 - деталь, 5.0 - сборка
    '''
    def __init__(self, file_path:str, doc_type:float, marking:str, name:str):
        super().__init__()
        self.file_path = file_path
        self.doc_type = doc_type
        self.marking = marking
        self.name = name

        self.make_document()

    def make_document(self):
        #создание документа в зависимости от типа
        try:
            iDocuments = self.app.Documents
            iKompasDocument = iDocuments.Add(self.doc_type, False)
            iKompasDocument3D = self.module.IKompasDocument3D(iKompasDocument)
            iPart7 = iKompasDocument3D.TopPart

            #добавление обозначения и наименования
            doc_item = KompasItem(iPart7)
            doc_item.set_prp_value(4.0, self.marking)
            doc_item.set_prp_value(5.0, self.name)

            iKompasDocument.SaveAs(self.file_path)
            iKompasDocument.Close(0)

        except Exception as e:
            print(e)
            return

class k2DMaker(KompasAPI):
    def __init__(self, local_file_path, network_file_path, main_window_instance):
        super().__init__()
        self.local_file_path = local_file_path
        self.network_file_path = network_file_path
        self.main_window = main_window_instance

        #определение локального и сетевого путей
        local_path_parts = self.local_file_path.split('\\')
        self.source_name = local_path_parts[-1]
        self.local_dir_path = '\\'.join(local_path_parts[:-1])

        network_path_parts = self.network_file_path.split('/')
        self.network_dir_path = '/'.join(network_path_parts[:-1])

        self.network_cdw_path = self.network_file_path[:-4]+'.cdw'

        self.db_path = project_root+'\\databases\\CADFolder.db'

        self.create_doc()

    def create_doc(self):
        iDocuments = self.app.Documents
        iKompasDocument = iDocuments.Add(1, True)
        #сохранение чертежа на локальном диске
        drawing_path = self.local_file_path[:-4]+'.cdw'
        iKompasDocument.SaveAs(drawing_path)
        
        try:
            shutil.copy2(drawing_path, self.network_dir_path)
            last_modified = datetime.fromtimestamp(os.path.getmtime(drawing_path)).isoformat()
            name = self.source_name[:-4]+'.cdw'
            status = getuser()
            self.user_db_path = project_root+'\\databases\\CADFolder_{}.db'.format(status)

            with sqlite3.connect(self.db_path) as conn, sqlite3.connect(self.user_db_path) as user_conn:
                user_cursor = user_conn.cursor()
                cursor = conn.cursor()
                cursor.execute('''INSERT INTO file_structure
                                (name, network_path, status, type, last_modified)
                                VALUES (?,?,?,?,?)''',
                                (name, self.network_cdw_path, status, 'file', last_modified))
                user_cursor.execute('''INSERT INTO file_structure
                            (name, local_path, status, type, last_modified)
                            VALUES (?,?,?,?,?)''',
                            (name, drawing_path, status, 'file', last_modified))
                user_conn.commit()
                conn.commit()
                self.main_window.update_treeview()
        
        except Exception as e:
            print('Ошибка копирования файла: {}'.format(e))

