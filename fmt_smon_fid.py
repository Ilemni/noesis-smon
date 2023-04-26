from inc_noesis import *
from os.path import isfile


# -----------
# EGMesh is a chunk containing data for a model of one or more meshes, and texture names.
# Textures of the matching name are expected to be present.
# .FID is a file format that contains only an EGMesh chunk.
# ----------


def registerNoesisTypes():
    handle = noesis.register("Summoners War Static Mesh", ".fid")
    noesis.setHandlerTypeCheck(handle, fid_check_type)
    noesis.setHandlerLoadModel(handle, fid_load_model)
    return 1


FID_HEADER = "EGMesh"


def fid_check_type(data):
    """
    For use by Noesis.
    :type data: bytes
    :rtype: int
    """

    if len(data) < 6:
        return 0
    bs = NoeBitStream(data)

    signature = bs.readBytes(6).decode()
    return 1 if signature == FID_HEADER else 0


def fid_load_model(data, models):
    """
    :type models: list[NoeModel]
    :type data: bytes
    :rtype: int
    """

    bs = NoeBitStream(data)

    fid_signature = bs.readBytes(12).decode().rstrip('\x00')
    if fid_signature != FID_HEADER:
        raise Exception("[FID] Unexpected signature: {0}".format(fid_signature))

    print("[FID:Signature]: {0}".format(fid_signature))

    unk1 = bs.readBytes(0x10)
    # print("[FID:Header:Unk1] {0}".format(bytes_str(unk1, 4)))

    # ================================= Texture paths ================================ #

    texture_count = bs.readInt()
    texture_paths = []

    for x in range(texture_count):
        unk2 = bs.readBytes(0x2C)
        # print("[FID:Texture {0}:Unk] {1}".format(x, bytes_str(unk2, 4)))
        has_texture = bs.readInt()
        if has_texture:
            texture_path = bs.readBytes(0x40).decode().rstrip('\x00')
            bs.seek(0xBC, NOESEEK_REL)
            texture_paths.append(texture_path)
        else:
            texture_paths.append(None)

    print("[FID:Textures] Count: {0} | Values: {1}".format(len(texture_paths), texture_paths))

    unk3 = bs.readBytes(0x18)
    # print("[FID:Textures:Unk3] {0}".format(bytes_str(unk3, 4)))

    # =================================== Meshes ==================================== #

    mesh_count = bs.readInt()
    print("[FID:Meshes] Count: {0} | File Position: {1}".format(mesh_count, hex(bs.tell())))

    model = NoeModel()
    model.setModelMaterials(NoeModelMaterials([], []))

    for x in range(mesh_count):
        # print("[FID:Mesh {0}] File Position: {1}".format(x, hex(bs.tell())))
        mesh_name = bs.readBytes(0x40).decode().rstrip('\x00')
        bs.seek(0x40, NOESEEK_REL)
        mesh_name_2 = bs.readBytes(0x40).decode().rstrip('\x00')
        bs.seek(0x40, NOESEEK_REL)
        texture_index = bs.readInt()
        bs.seek(0xC, NOESEEK_REL)

        vert_count = bs.readInt()
        vert_array_size = bs.readInt()  # This should always be vert_count * 12
        vert_positions = []
        for _ in range(vert_count):
            vert_positions.append(NoeVec3((bs.readFloat(), bs.readFloat(), bs.readFloat())))

        uv_size = bs.readInt()
        uv_data = []
        for _ in range(int(uv_size / 8)):
            uv_data.append(NoeVec3((bs.readFloat(), bs.readFloat() * -1, 0)))

        uv2_slot = bs.readInt()
        uv2_data = []
        uv2_size = 0
        if uv2_slot != 0:
            uv2_size = bs.readInt()
            for _ in range(int(uv2_size / 8)):
                uv2_data.append(NoeVec3((bs.readFloat(), bs.readFloat() * -1, 0)))

        # ============================= Create mesh ================================== #

        # File does not include triangle data. Rapi expects it, so we have to fake it.
        mesh = NoeMesh(list(range(vert_count)), vert_positions)
        model.meshes.append(mesh)
        mesh.setName(mesh_name)
        mesh.setUVs(uv_data)
        if uv2_slot != 0:
            mesh.setUVs(uv2_data, uv2_slot)

        # =============================== Logging ==================================== #

        # print("[FID:Mesh {0}] Name: {1} | Texture: {2} | Verts: {3} | UV1: {4} | Has UV2: {5}"
        #       .format(x, mesh_name, texture_paths[texture_index], vert_count, uv_size, uv2_slot) +
        #       ("" if not uv2_slot else " | UV2: {0}".format(uv2_size)))
        # if mesh_name_2 != mesh_name:
        #     print("[FID:Mesh {0}] Name: {1} (second stored name is different)".format(x, mesh_name_2))

        # ============================= Get Textures ================================= #

        tex_path = texture_paths[texture_index]
        tex_filepath = noesis.getSelectedDirectory() + "\\" + tex_path
        if isfile(tex_filepath):
            texture = rapi.loadExternalTex(tex_filepath)
            texture.name = tex_path
            material_name = "Material_" + tex_path
            material = NoeMaterial(material_name, texture.name)

            model.modelMats.matList.append(material)
            model.modelMats.texList.append(texture)
            mesh.setMaterial(material_name)
        else:
            noesis.logError("[ERROR] [FID:Mesh {0}] Missing texture {1}\n".format(x, tex_filepath))

    models.append(model)
    return 1


def bytes_str(bit_array, split=1):
    """
    Returns a clean string representation of the bytes object
    Example: [0x00, 0xFF, 0x7B] returns "00 FF 7B"
    :type bit_array: bytes | list[byte]
    :param bit_array: Bytes to get a string representation from
    :rtype: str
    :return: String that represents the bytes object
    """
    out_string = ""
    for idx in range(len(bit_array)):
        x = bit_array[idx]
        h = hex(x)[2:]
        if len(h) == 1:
            out_string += "0"
        out_string += str.upper(h)
        if idx % split == split - 1:
            out_string += " "
    return out_string
