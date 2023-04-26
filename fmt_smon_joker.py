from inc_noesis import *


# -----------
# Some image files are in a proprietary format that stores up to two images of either JPG or PNG.
# The first image is a diffuse texture.
# The second image is an opacity/transparency texture, if present.
# ----------


def registerNoesisTypes():
    handle = noesis.register("Summoners War Image", ".png")
    noesis.setHandlerTypeCheck(handle, joker_check_type)
    noesis.setHandlerLoadRGBA(handle, load_joker_file)
    return 1


JOKER_HEADER = "Joker"


def joker_check_type(data):
    """
    For use by Noesis.
    :type data: bytes
    :rtype: int
    """
    return is_joker_chunk(NoeBitStream(data)) if len(data) >= 5 else 0


def is_joker_chunk(bs):
    """
    Checks whether the stream is at the start of a Joker chunk.
    :type bs: NoeBitStream
    :return: 1 if this is a Joker chunk, otherwise 0
    :rtype: int
    """
    joker = bs.readBytes(5)
    bs.seek(-5, NOESEEK_REL)
    try:
        return 1 if joker.decode() == JOKER_HEADER else 0
    except UnicodeDecodeError:
        return 0


def load_joker_file(data, textures):
    """
    For use by Noesis.
    :type data: bytes
    :type textures: list[NoeTexture]
    :rtype: int
    """
    if joker_check_type(data) == 0:
        return 0

    bs = NoeBitStream(data)
    diffuse, alpha = load_joker(bs)

    if diffuse is not None:
        textures.append(diffuse)

    if alpha is not None:
        textures.append(alpha)

    return 1


def load_joker(bs):
    """
    Loads NoeTextures from the Joker chunk in the stream.
    :type bs: NoeBitStream
    :rtype: tuple[NoeTexture | None, NoeTexture | None]
    """
    bs.seek(8, NOESEEK_REL)  # 6 bytes null terminated string "JOKER", 2 bytes 0x1F01
    diffuse_size = bs.readInt()
    alpha_size = bs.readInt()

    diffuse_tex = None
    if diffuse_size > 0:
        diffuse_bytes = bs.readBytes(diffuse_size)
        diffuse_tex = rapi.loadTexByHandler(diffuse_bytes, ".jpg")

    alpha_tex = None
    if alpha_size > 0:
        alpha_bytes = bs.readBytes(alpha_size)
        alpha_tex = rapi.loadTexByHandler(alpha_bytes, ".jpg")

    return diffuse_tex, alpha_tex
