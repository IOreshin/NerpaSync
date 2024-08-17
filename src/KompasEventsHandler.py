# -*- coding: utf-8 -*-

import threading
import pythoncom
import win32com.client
import time

class KompasFrameHandler(threading.Thread):
    '''
    Класс для получения имени файла и отправки сообщений о том, что документ изменился
    '''
    def __init__(self, event_queue):
        super().__init__()
        self.event_queue = event_queue
        self.daemon = True  # Поток завершается при завершении основного приложения
        self.app = None
        self.stop_event = threading.Event()
        self.last_doc_name = None

    def run(self):
        pythoncom.CoInitialize()
        try:
            self.app = win32com.client.Dispatch("Kompas.Application.7")
            self.check_document_status()
        except Exception as e:
            self.event_queue.put("Ошибка при подключении к Kompas: {}".format(e))
        finally:
            pythoncom.CoUninitialize()

    def check_document_status(self):
        while not self.stop_event.is_set():
            try:
                iKompasDocument = self.app.ActiveDocument
                if iKompasDocument:
                    doc_name = iKompasDocument.Name
                    if doc_name != self.last_doc_name:
                        self.event_queue.put(doc_name) #возвращение имени документа
                        self.last_doc_name = doc_name
            except Exception as e:
                self.event_queue.put("Ошибка при доступе к документу: {}".format(e))
            time.sleep(0.5)  # Периодическая проверка каждые 0,5 секунд

    def stop(self):
        self.stop_event.set()