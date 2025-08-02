from inc_noesis import *
from fmt_smon_pmm import load_pmm_data, pmm_check_signature, pmm_check_ciphered, as_deciphered
from fmt_smon_plm import load_plm_animation
from fmt_smon_joker import load_joker, is_joker_chunk
from inc_smon import peek_bytes


# ----------
# DAT is a file format that contains the following data:
# 4 bytes size of header chunk
# The Header chunk (most data unknown, contains ciphered filename)
#
# 4 bytes size of PMM chunk
# The PMM chunk (skinned mesh), may be ciphered with a simple substitution cipher
#
# 4 bytes size of PLM chunk
# The PLM chunk (armature, animations)
#
# List of Joker chunks with in-game element IDs (diffuse and optional alpha texture)
# ----------


def registerNoesisTypes():
    handle = noesis.register("Summoners War Character", ".dat")
    noesis.setHandlerTypeCheck(handle, dat_check_type)
    noesis.setHandlerLoadModel(handle, dat_load_model)
    return 1


def dat_check_type(data):
    # Check type by skipping header chunk then checking PMM chunk signature
    if len(data) < 8:
        return 0
    bs = NoeBitStream(data)

    # Header size is usually 0x20 + len(filename_without_extension), sometimes with an extra byte
    # Part of the header contains the ciphered filename

    header_size = bs.readInt()
    if header_size < 32 or header_size > len(data) + 8:
        return 0

    # Check if PMM chunk signature is valid
    bs.seek(header_size + 8, NOESEEK_ABS)
    pmm_header = bs.readBytes(3)
    pmm_version = bs.readBytes(1)

    return pmm_check_signature(pmm_header, pmm_version, True)


def dat_load_model(data, models):
    noesis.logPopup()
    bs = NoeBitStream(data)

    # ================================= Header data= ================================= #

    header_size = bs.readUInt()
    header = DatHeader(bs, header_size)
    print("[DAT:Header] Embedded header name: {0}".format(header.name))

    # =================================== PMM data =================================== #

    pmm_size = bs.readUInt()
    # print("[DAT:PMM] File Position: {0}, Size: {1}".format(hex(bs.tell()), hex(pmm_size)))

    # PMM signature: chunk may be ciphered, decipher if necessary
    pmm_header = peek_bytes(bs, 3)

    if pmm_check_ciphered(pmm_header):
        decipher_pmm(bs, pmm_size)

    pmm_data = load_pmm_data(bs)

    # =================================== PLM data =================================== #

    bs.seek(header_size + 4 + pmm_size + 4, NOESEEK_ABS)
    plm_size = bs.readInt()

    # print("[DAT:PLM] File Position: {0}, Size: {1}".format(hex(bs.tell()), hex(plm_size)))
    bones, animations = load_plm_animation(bs, pmm_data.scale_divider)

    # ================================= Texture data ================================= #

    bs.seek(header_size + 4 + pmm_size + 4 + plm_size + 4, NOESEEK_ABS)
    # print("[DAT:Tex] File Position: {0}".format(hex(bs.tell())))
    materials, textures = load_textures(bs, header, pmm_data)

    # ================================= Create model ================================= #

    model = pmm_data.construct_model()
    model.meshes[0].setName(header.name)
    model.setBones(bones)
    if animations is not None:
        model.setAnims(animations)
    model.setModelMaterials(NoeModelMaterials(textures, materials))

    models.append(model)
    return 1


def load_textures(bs, header, pmm_data):
    textures = []
    materials = []
    while not bs.checkEOF():
        # Some models may have only one image (special_mdl_*.dat)
        # And do not use a material_id system
        multi_material = True
        material_id = bs.readInt()
        if material_id > 255:
            multi_material = False
            chunk_size = material_id
            material_id = 0
        else:
            chunk_size = bs.readInt()
        if chunk_size == 0:
            continue

        texture_name = header.name + ("_" + material_names[material_id] if multi_material else "")

        diffuse_texture, alpha_texture = load_joker(bs) if is_joker_chunk(bs) else (
            rapi.loadTexByHandler(bs.readBytes(chunk_size), ".png"), None)

        diffuse_texture.name = texture_name + "_diffuse"
        textures.append(diffuse_texture)

        if alpha_texture is not None:
            alpha_texture.name = texture_name + "_alpha"
            textures.append(alpha_texture)

        # print("[DAT:Tex:Material {0}] Size: {1} | Format: {2} | Has Alpha: {3}"
        #       .format(material_id, chunk_size, file_extension, alpha_texture is not None))
        material_name = "Material {0}".format(material_id) if multi_material else "Material"
        material = NoeMaterial(material_name, diffuse_texture.name)
        if alpha_texture is not None:
            material.setOpacityTexture(alpha_texture.name)

        materials.append(material)

        pmm_data.add_material(material)
    return materials, textures


def decipher_pmm(bs, size):
    """
    :type bs: NoeBitStream
    :param bs: The bitstream containing the PMM chunk
    :type size: int
    :param size: The size of the PMM chunk to decipher
    """
    ciphered_pmm_chunk = peek_bytes(bs, size)
    deciphered = as_deciphered(ciphered_pmm_chunk)
    bs.writeBytes(deciphered)
    bs.seek(-size, NOESEEK_REL)


class DatHeader:
    def __init__(self, bs, header_len):
        start = bs.tell()
        # 0x11 bytes unknown, mostly identical across files
        bs.seek(0x11, NOESEEK_REL)

        # variable bytes original filename, todo: delimiter
        self.name = ""
        while True:
            c = filename_decipher[bs.readUByte()]
            if c == 0x00:
                break
            try:
                self.name += chr(c)
            except UnicodeDecodeError:
                break
        self.name = self.name.rstrip('\'')
        # variable bytes remaining header
        bs.seek(start + header_len, NOESEEK_ABS)


# Incomplete cipher, some letters/numbers have not been used
filename_decipher = bytearray([
    0xFE, 0x00, 0x00, 0x7A, 0x00, 0x00, 0x00, 0x00, 0x00, 0x31, 0x00, 0x00, 0x00, 0x30, 0x00, 0x00,
    0x00, 0x00, 0x62, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x35, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x6B, 0x00, 0x00, 0x00, 0x75, 0x79, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x74, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x29, 0x00, 0x00, 0x33, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x6F, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x28, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x6D, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x27, 0x00, 0x00, 0x00, 0x61, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x6A, 0x63, 0x00, 0x00, 0x00, 0x00, 0x00, 0x70, 0x00, 0x00, 0x00, 0x73, 0x00, 0x77,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x5F, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x66, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x32, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x68, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x72, 0x76, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x64, 0x67, 0x00, 0x00, 0x00, 0x6C,
    0x00, 0x6E, 0x00, 0x00, 0x00, 0x00, 0x78, 0x2E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x69, 0x00, 0x00, 0x65, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x34, 0x00
])

material_names = {
    1: "water",
    2: "fire",
    3: "wind",
    4: "light",
    5: "dark",
    6: "pure"
}
