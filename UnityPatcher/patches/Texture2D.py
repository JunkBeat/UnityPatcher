from typing import Optional

from PIL import Image
from UnityPy.classes import Texture2D

from enums import TextureCompressionQuality as Quality
from .TextureConverter import generate_mipmaps, image_to_raw, image_to_texture2d


def _Texture2D_set_image(
    self: Texture2D,
    img_path: str,
    raw_mode: bool = False,
    compression_quality: Quality = Quality.BEST,
    target_format: Optional[int] = None,
    mipmap_count: int = 1,
):
    if not img_path:
        raise Exception("No image provided")

    if not target_format:
        target_format = self.m_TextureFormat

    img = Image.open(img_path)

    img_data, tex_format = (
        image_to_raw(img, target_format)
        if raw_mode or any(dimension % 4 != 0 for dimension in img.size)
        else image_to_texture2d(img, target_format, compression_quality)
    )

    if mipmap_count > 1:
        img_data, mipmap_count = generate_mipmaps(
            img, img_data, mipmap_count, target_format, compression_quality
        )

    if self.version[:2] < (5, 2):  # 5.2 down
        self.m_MipMap = mipmap_count > 1
    else:
        self.m_MipCount = mipmap_count

    self.image_data = img_data

    self.m_CompleteImageSize = len(img_data)
    self.m_TextureFormat = tex_format
    self.m_Width, self.m_Height = img.size


def _Texture2D_save_via_tree(self: Texture2D):
    tree = self.read_typetree()
    if not tree:
        raise Exception("Typetree is None")

    if "m_MipMap" in tree:
        tree["m_MipMap"] = self.m_MipMap
    else:
        tree["m_MipCount"] = self.m_MipCount

    tree.update(
        {
            "m_TextureFormat": self.m_TextureFormat,
            "m_CompleteImageSize": len(self.image_data),
            "image data": self.image_data,
            "m_Width": self.m_Width,
            "m_Height": self.m_Height,
            "m_StreamData": {"offset": 0, "size": 0, "path": ""},
        }
    )

    self.reader.save_typetree(tree)


Texture2D.set_image = _Texture2D_set_image  # replacing original method
Texture2D.save_via_tree = _Texture2D_save_via_tree
