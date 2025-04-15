from .BaseManager import BaseManager


# For old ~ Unity 2020
class Mesh(BaseManager):
    def __init__(self, data):
        super().__init__(data)
        self.name = data.name

    def export(self, path: str = None):
        if self.data.version > (2019,):
            mesh = self.data.export()
            if mesh:
                dest = self.get_destination_path(self.name, ".obj", path)
                super().save(dest, mesh.encode("utf-8"))
        else:
            super().export_dump(path)

    def import_(self, *args):
        raise NotImplementedError("Import is not supported")
