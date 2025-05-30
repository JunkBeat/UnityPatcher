from typing import Tuple, Union

import astc_encoder
from PIL import Image
from UnityPy.enums import TextureFormat as TF

from enums import TextureCompressionQuality as Quality
from tools import compress_image_to_bc


def image_to_texture2d(
    img: Image.Image,
    target_texture_format: Union[TF, int],
    quality: Quality = Quality.BEST,
    flip: bool = True,
) -> Tuple[bytes, TF]:
    if isinstance(target_texture_format, int):
        target_texture_format = TF(target_texture_format)

    import etcpak

    if flip:
        img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

    # DXT (BCnEncoder.NET)
    if target_texture_format in [TF.DXT1, TF.DXT1Crunched]:
        enc_img = compress_image_to_bc(img, "BC1", quality)
        tex_format = TF.DXT1
    elif target_texture_format in [TF.DXT3]:
        enc_img = compress_image_to_bc(img, "BC2", quality)
        tex_format = TF.DXT3
    elif target_texture_format in [TF.DXT5, TF.DXT5Crunched, TF.BC7]:
        enc_img = compress_image_to_bc(img, "BC3", quality)
        tex_format = TF.DXT5
    elif target_texture_format in [TF.BC4]:
        enc_img = compress_image_to_bc(img, "BC4", quality)
        tex_format = TF.BC4
    elif target_texture_format in [TF.BC5]:
        enc_img = compress_image_to_bc(img, "BC5", quality)
        tex_format = TF.BC5
    # Disabled because the compression is very long and seems incorrect
    # elif target_texture_format in [TF.BC7]:
    #     enc_img = compress_image_to_bc(img, "BC7", quality)
    #     tex_format = TF.BC7
    
    # ETC (etcpak)
    elif target_texture_format in [TF.ETC_RGB4, TF.ETC_RGB4Crunched, TF.ETC_RGB4_3DS]:
        raw_img = img.tobytes("raw", "RGBA")
        enc_img = etcpak.compress_etc1_rgb(raw_img, img.width, img.height)
        tex_format = TF.ETC_RGB4
    elif target_texture_format == TF.ETC2_RGB:
        raw_img = img.tobytes("raw", "RGBA")
        enc_img = etcpak.compress_etc2_rgb(raw_img, img.width, img.height)
        tex_format = TF.ETC2_RGB
    elif (
        target_texture_format in [TF.ETC2_RGBA8, TF.ETC2_RGBA8Crunched, TF.ETC2_RGBA1]
        or "_RGB_" in target_texture_format.name
    ):
        raw_img = img.tobytes("raw", "RGBA")
        enc_img = etcpak.compress_etc2_rgba(raw_img, img.width, img.height)
        tex_format = TF.ETC2_RGBA8
    # ASTC (astc_encoder)
    elif target_texture_format.name.startswith("ASTC"):
        raw_img = img.tobytes("raw", "RGBA")

        block_size = tuple(
            map(int, target_texture_format.name.rsplit("_", 1)[1].split("x"))
        )

        config = astc_encoder.ASTCConfig(
            astc_encoder.ASTCProfile.LDR, *block_size, 1, 100
        )
        context = astc_encoder.ASTCContext(config)
        raw_img = astc_encoder.ASTCImage(
            astc_encoder.ASTCType.U8, img.width, img.height, 1, raw_img
        )
        if img.mode == "RGB":
            tex_format = getattr(TF, f"ASTC_RGB_{block_size[0]}x{block_size[1]}")
        else:
            tex_format = getattr(TF, f"ASTC_RGBA_{block_size[0]}x{block_size[1]}")

        swizzle = astc_encoder.ASTCSwizzle.from_str("RGBA")
        enc_img = context.compress(raw_img, swizzle)
        tex_format = target_texture_format
    else:
        return image_to_raw(img, target_texture_format, flip=False)

    return enc_img, tex_format


def image_to_raw(
    img: Image.Image, target_texture_format: Union[TF, int], flip: bool = True
) -> Tuple[bytes, TF]:
    if isinstance(target_texture_format, int):
        target_texture_format = TF(target_texture_format)

    if flip:
        img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

    # A
    if target_texture_format == TF.Alpha8:
        enc_img = img.tobytes("raw", "A")
        tex_format = TF.Alpha8
    # R - should probably be moerged into #A, as pure R is used as Alpha
    # but need test data for this first
    elif target_texture_format in [
        TF.R8,
        TF.R16,
        TF.RHalf,
        TF.RFloat,
        TF.EAC_R,
        TF.EAC_R_SIGNED,
    ]:
        enc_img = img.tobytes("raw", "R")
        tex_format = TF.R8
    # RGBA
    elif target_texture_format in [
        TF.RGB565,
        TF.RGB24,
        TF.RGB9e5Float,
        TF.PVRTC_RGB2,
        TF.PVRTC_RGB4,
        TF.ATC_RGB4,
    ]:
        try:
            enc_img = img.tobytes("raw", "RGB")
        except ValueError:
            img = img.convert("RGB")
            enc_img = img.tobytes("raw", "RGB")

        tex_format = TF.RGB24
    # everything else defaulted to RGBA
    else:
        try:
            enc_img = img.tobytes("raw", "RGBA")
        except ValueError:
            img = img.convert("RGBA")
            enc_img = img.tobytes("raw", "RGBA")
            
        tex_format = TF.RGBA32

    return enc_img, tex_format


def generate_mipmaps(
    img: Image.Image,  # source image
    data: bytes,  # bytes object where to write mipmaps
    mipmap_count: int,
    target_format: TF,
    compression_quality: Quality = Quality.BEST,
) -> Tuple[bytes, int]:
    mips_data = bytearray()

    if mipmap_count > 1:
        width, height = img.size
        re_img = img
        for i in range(mipmap_count - 1):
            width //= 2
            height //= 2
            if width < 4 or height < 4:
                mipmap_count = i + 1
                break
            re_img = re_img.resize(
                (width, height), Image.BILINEAR
            )  # bilinear instead of bicubic
            mips_data.extend(
                image_to_texture2d(re_img, target_format, compression_quality)[0]
            )

    new_data = data + bytes(mips_data)
    return new_data, mipmap_count
