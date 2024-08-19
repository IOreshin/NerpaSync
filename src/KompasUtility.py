# -*- coding: utf-8 -*-

import os, sys
import json
import pythoncom
from win32com.client import Dispatch, gencache
from tkinter.messagebox import showinfo
import threading

 
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
    def __init__(self, open_state:bool,file_path:str):
        super().__init__()
        self.file_path = file_path
        self.open_state = open_state
        self.open_doc()

    def open_doc(self):
        iDocuments = self.app.Documents
        iDocuments.Open(self.file_path, True, self.open_state)
