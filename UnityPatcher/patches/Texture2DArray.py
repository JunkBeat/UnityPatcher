import logging
from typing import List

from PIL import Image
from UnityPy.classes import Texture2DArray
from UnityPy.enums.GraphicsFormat import GRAPHICS_TO_TEXTURE_MAP
from UnityPy.helpers.ResourceReader import get_resource_data

from enums import TextureCompressionQuality as Quality
from .TextureConverter import generate_mipmaps, image_to_raw, image_to_texture2d


def _Texture2DArray_image_data_getter(self: Texture2DArray):
    data = getattr(self, "image data", None)
    if data is None:
        data = get_resource_data(
            self.m_StreamData.path,
            self.assets_file,
            self.m_StreamData.offset,
            self.m_StreamData.size,
        )
    return data


def _Texture2DArray_image_data_setter(self: Texture2DArray, value: bytes):
    setattr(self, "image data", value)
    self.reset_streamdata()


def _Texture2DArray_reset_streamdata(self: Texture2DArray):
    if not self.m_StreamData:
        return
    self.m_StreamData.offset = 0
    self.m_StreamData.size = 0
    self.m_StreamData.path = ""


def _Texture2DArray_set_images(
    self: Texture2DArray,
    imgs_path: List[str],
    raw_mode: bool = False,
    compression_quality: Quality = Quality.BEST,
    mipmap_count: int = 1,
):
    if not imgs_path:
        raise Exception("No images provided")

    target_format = GRAPHICS_TO_TEXTURE_MAP.get(self.m_Format)

    if not target_format:
        raise NotImplementedError(f"GraphicsFormat {self.m_Format} not supported yet")

    if len(imgs_path) != self.m_Depth:
        raise ValueError(
            f"Incorrect number of images. Expected {self.m_Depth}, got {len(imgs_path)}"
        )

    texture_to_graphics_map = {v: k for k, v in GRAPHICS_TO_TEXTURE_MAP.items()}
    new_image_data = bytearray()

    for i, image_path in enumerate(imgs_path[: self.m_Depth]):
        logging.info("Packing progress: %d/%d", i + 1, self.m_Depth)

        img = Image.open(image_path)

        if img.size != (self.m_Width, self.m_Height):
            raise ValueError(
                f"Incorrect image size. Expected {self.m_Width}x{self.m_Height}, got {img.size} (index: {i})"
            )

        img_data, tex_format = (
            image_to_raw(img, target_format)
            if (raw_mode or any(dimension % 4 != 0 for dimension in img.size))
            else image_to_texture2d(img, target_format, compression_quality)
        )

        if mipmap_count > 1:
            img_data, mipmap_count = generate_mipmaps(
                img, img_data, mipmap_count, target_format, compression_quality
            )

        new_image_data.extend(img_data)

    self.image_data = bytes(new_image_data)
    self.m_DataSize = len(new_image_data)
    self.m_Format = texture_to_graphics_map.get(tex_format)
    self.m_MipCount = mipmap_count


def _Texture2DArray_save_via_tree(self: Texture2DArray):
    tree = self.read_typetree()
    if not tree:
        raise Exception("Typetree is None")

    tree.update(
        {
            "m_Format": self.m_Format,
            "m_MipCount": self.m_MipCount,
            "m_DataSize": self.m_DataSize,
            "image data": self.image_data,
            "m_StreamData": {"offset": 0, "size": 0, "path": ""},
        }
    )
    self.reader.save_typetree(tree)


Texture2DArray.image_data = property(
    _Texture2DArray_image_data_getter, _Texture2DArray_image_data_setter
)
Texture2DArray.reset_streamdata = _Texture2DArray_reset_streamdata
Texture2DArray.set_images = _Texture2DArray_set_images
Texture2DArray.save_via_tree = _Texture2DArray_save_via_tree
