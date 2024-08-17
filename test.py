



from src.KompasUtility import KompasAPI

class redraw(KompasAPI):
    def __init__(self):
        super().__init__()
        self.redraw_doc()

    def redraw_doc(self):
        doc = self.app.ActiveDocument
        doc_path = doc.PathName
        doc.Close(0)
        iDocuments = self.app.Documents
        iDocuments.Open(doc_path, True)


redraw()





