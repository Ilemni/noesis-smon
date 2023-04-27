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

    for x in range(mesh_count):
        # print("[FID:Mesh {0}] File Position: {1}".format(x, hex(bs.tell())))
        mesh_name = bs.readBytes(0x40).decode().rstrip('\x00')
        bs.seek(0xC0, NOESEEK_REL)
        texture_index = bs.readInt()
        bs.seek(0xC, NOESEEK_REL)

        fid_data = FidData(mesh_name)

        fid_data.vertex_count = bs.readInt()
        fid_data.vertex_bytes = read_buffer(bs)
        fid_data.uv1_bytes = read_buffer(bs)

        fid_data.uv2_slot = bs.readInt()
        if fid_data.uv2_slot != 0:
            fid_data.uv2_bytes = read_buffer(bs)

        # =============================== Logging ==================================== #

        # print("[FID:Mesh {0}] Name: {1} | Texture: {2} | Verts: {3} | UV1: {4} | Has UV2: {5}"
        #       .format(x, mesh_name, texture_paths[texture_index], vert_count, uv_size, uv2_slot) +
        #       ("" if not uv2_slot else " | UV2: {0}".format(uv2_size)))

        # ============================= Get Textures ================================= #

        texture_filename = texture_paths[texture_index]
        texture_filepath = noesis.getSelectedDirectory() + "\\" + texture_filename
        if not isfile(texture_filepath):
            noesis.logError("[ERROR] [FID:Mesh {0}] Missing texture {1}\n".format(x, texture_filepath))
        else:
            fid_data.texture = rapi.loadExternalTex(texture_filepath)
            fid_data.texture.name = texture_filename
            fid_data.material = NoeMaterial("Material_" + texture_filename, fid_data.texture.name)

        # ============================= Create model ================================= #

        model = fid_data.construct_model()
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


class FidData:
    """
    Contains data stored in a Summoners War PMM chunk.
    :cvar vertex_count: Number of vertices in the model. Stored in file as int.
    :cvar vertex_bytes: Vertex position data. Stored in file as 3x float per item.
    :cvar uv_bytes: UV position data. Stored in file as 2x float per item.
    :cvar uv2_bytes: UV position data. Stored in file as 2x float per item.
    :cvar material: NoeMaterial
    :cvar texture: NoeTexture
    """

    model_name = None
    vertex_count = 0
    vertex_bytes = []
    uv1_bytes = []
    uv2_slot = 0
    uv2_bytes = None
    material = None
    texture = None

    def __init__(self, model_name):
        self.model_name = model_name

    def construct_model(self):
        """
        Constructs the model from member properties.
        :rtype: NoeModel
        """
        rapi.rpgCreateContext()
        rapi.rpgBindPositionBuffer(self.vertex_bytes, noesis.RPGEODATA_FLOAT, 12)
        rapi.rpgBindUV1Buffer(self.uv1_bytes, noesis.RPGEODATA_FLOAT, 8)
        if self.uv2_bytes is not None:
            rapi.rpgBindUVXBuffer(self.uv2_bytes, noesis.RPGEODATA_FLOAT, 8, self.uv2_slot, 1)

        if self.material.name is not None:
            rapi.rpgSetMaterial(self.material.name)

        # Rapi requires tris. Fid contains no tris. We have to fake it.
        # Byte array where every 4 bytes represents an int of ascending value
        fake_tris = bytearray()
        for x in range(self.vertex_count):
            fake_tris.append(x % 256)
            fake_tris.append((x >> 8) % 256)
            fake_tris.append((x >> 16) % 256)
            fake_tris.append((x >> 24) % 256)

        rapi.rpgCommitTriangles(fake_tris, noesis.RPGEODATA_UINT, self.vertex_count, noesis.RPGEO_TRIANGLE, 1)

        model = rapi.rpgConstructModel()
        model.meshes[0].setName(self.model_name)
        model.setModelMaterials(NoeModelMaterials([self.texture], [self.material]))

        # UVs are flipped, we need to flip the Y component here.
        for item in model.meshes[0].uvs:
            item[1] = -item[1]
        return model


def read_buffer(bs):
    """
    First reads an int for length of buffer, then reads the length
    :type bs: NoeBitStream
    :rtype: bytes
    """
    buffer_size = bs.readInt()
    return bs.readBytes(buffer_size)
