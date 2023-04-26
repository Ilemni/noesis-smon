import string

import fmt_smon_joker
from inc_noesis import *
from os.path import isfile, basename
from fmt_smon_plm import plm_check_type, load_plm_animation

# -----------
# PMM is a chunk containing data for a single skinned mesh.
# Bone and animation data are separately contained in a PLM chunk.
#
# .PMOD is a file format that contains only a PMM chunk.
# .PLIV is a file format that contains only a PLM chunk.
# .DAT is a file format that contains both a PMM and PLM chunk, and textures.
# ----------


def registerNoesisTypes():
    """Register the format in this plugin
    :rtype: int
    """

    handle = noesis.register("Summoners War Skinned Mesh", ".pmod")
    noesis.setHandlerTypeCheck(handle, pmm_check_type)
    noesis.setHandlerLoadModel(handle, load_pmm_from_pmod)
    return 1


PMM_HEADER_V1 = 'PMM$'
PMM_HEADER_V2 = 'PMM#'  # 1 less byte after reading scale_divider
PMM_HEADER_V3 = 'PMM%'  # No apparent changes
PMM_HEADER_V4 = 'PMM"'  # Same as V2
PMM_HEADER_V1_CIPHERED = b'\xA6\x8A\x8A\xC8'  # Ciphered PMM$
PMM_HEADER_V2_CIPHERED = b'\xA6\x8A\x8A\x48'  # Ciphered PMM#
PMM_HEADER_V3_CIPHERED = b'\xA6\x8A\x8A\x3C'  # Ciphered PMM%
PMM_HEADER_V4_CIPHERED = b'\xA6\x8A\x8A\xED'  # Ciphered PMM"

PMM_HEADERS = (PMM_HEADER_V1, PMM_HEADER_V2, PMM_HEADER_V3, PMM_HEADER_V4)
PMM_HEADERS_CIPHERED = (PMM_HEADER_V1_CIPHERED, PMM_HEADER_V2_CIPHERED, PMM_HEADER_V3_CIPHERED, PMM_HEADER_V4_CIPHERED)


def pmm_check_type(data):
    """
    For use by Noesis.
    :type data: bytes
    :rtype: int
    """

    if len(data) < 8:
        return 0
    bs = NoeBitStream(data)

    pmm = bs.readBytes(4)
    return pmm_check_signature(pmm, True)


def pmm_check_signature(pmm_signature, allow_cipher):
    """
    Check if the PMM chunk signature matches known signatures.
    :param pmm_signature:
    :type allow_cipher: bool
    :param allow_cipher: Whether to allow a ciphered signature to still pass.
    :return: 1 if signature matches known signature, otherwise 0.
    """

    try:
        if pmm_signature.decode() in PMM_HEADERS:
            return 1
    except UnicodeDecodeError:
        if pmm_check_ciphered(pmm_signature):
            if allow_cipher:
                return 1
            print("PMM is ciphered. Ensure PMM is deciphered")
        return 0


def pmm_check_ciphered(pmm_signature):
    """
    Check if the PMM chunk signature is ciphered.
    :type pmm_signature: bytes
    :rtype: int
    """

    return 1 if pmm_signature in PMM_HEADERS_CIPHERED else 0


def load_pmm_from_pmod(data, models):
    """
    For use by Noesis. Imports a .pmod file.
    :type models: list[NoeModel]
    :type data: bytes
    :rtype: int
    """

    bs = NoeBitStream(data)
    pmm_data = load_pmm_data(bs)
    model = pmm_data.construct_model()

    plm_filepath = noesis.getSelectedFile()[:-5] + ".pliv"
    if not isfile(plm_filepath):
        print("[ERROR] [PMM] Missing PLM file {0}".format(plm_filepath))
    else:
        plm_file = open(plm_filepath, "rb")
        plm_data = plm_file.read()
        plm_file.close()
        if plm_check_type(plm_data):
            bones, animations = load_plm_animation(NoeBitStream(plm_data), pmm_data.scale_divider)
            model.setBones(bones)
            model.setAnims(animations)

    tex_filepath = noesis.getSelectedFile()[:-5] + ".png"
    if not isfile(tex_filepath):
        print("Begin guessing")
        tex_filepath = pmod_guess_texture_file(tex_filepath)
    if not isfile(tex_filepath):
        print("[ERROR] [Tex] Missing PNG file " + tex_filepath +
              "\nThis script expects .pngs to have identical names or same but ending in \"_water\"" +
              "\nYou will have to find the correct PNG file on your own." +
              "\nIt should already be similarly named to the .pliv file.")
    else:
        diffuse_texture, alpha_texture = rapi.loadExternalTex(tex_filepath), None
        if diffuse_texture is None:
            tex_file = open(tex_filepath, "rb")
            tex_data = tex_file.read()
            tex_file.close()

            diffuse_texture, alpha_texture = fmt_smon_joker.load_joker(NoeBitStream(tex_data))
        diffuse_texture.name = basename(tex_filepath)
        material_name = "Material_" + diffuse_texture.name
        material = NoeMaterial(material_name, diffuse_texture.name)
        model.setModelMaterials(NoeModelMaterials([diffuse_texture], [material]))
        model.meshes[0].setMaterial(material_name)

    print(plm_filepath)
    models.append(model)
    return 1


def load_pmm_data(bs):
    """
    Processes the PMM chunk and returns its data.
    :type bs: NoeBitStream
    :rtype: PmmData
    """

    pmm_signature = bs.readBytes(4)
    if pmm_check_signature(pmm_signature, False) == 0:
        raise Exception("[PMM] Unexpected signature: {0}".format(pmm_signature))

    pmm_signature = pmm_signature.decode()
    print("[PMM:Signature]: {0}".format(pmm_signature))
    pmm_data = PmmData()

    unk1 = bs.readUShort()
    if unk1 != 0x11F:
        # print("[PMM:Header:Unk1] (normally 0x11F): {0}".format(bytes_str(unk1)))
        pass

    pmm_data.num_tris = bs.readUShort()
    # print("[PMM:Data:Tris] Count: {0}".format(pmm_data.num_tris))
    pmm_data.num_vertices = bs.readUShort()
    # print("[PMM:Data:Vertices] Count: {0}".format(pmm_data.num_vertices))
    unk2 = bs.readBytes(4)
    # print("[PMM:Header:Unk2] {0}".format(bytes_str(unk2)))
    pmm_data.scale_divider = bs.readUShort()
    if pmm_data.scale_divider != 1024:
        print("[PMM:Header:ScaleDivider] (normally 1024): {0}".format(pmm_data.scale_divider))

    unk3 = bs.readBytes(0x36 if pmm_signature in (PMM_HEADER_V2, PMM_HEADER_V4) else 0x37)
    # print("[PMM:Header:Unk3] {0}".format(bytes_str(unk3)))

    # cos_mdl_blacksmith_001 has offset for some reason
    # need more variety to figure this out properly
    if unk1 == 0x21F:
        unk4 = bs.readBytes(0xF)
        # print("[PMM:Unk4] {0}".format(bytes_str(unk4)))

    # print("[PMM:Data:Position] File Position: " + hex(bs.tell()))
    pmm_data.position_bytes = bs.readBytes(pmm_data.num_vertices * 12)
    # print("[PMM:Data:Normal] File Position: " + hex(bs.tell()))
    pmm_data.normal_bytes = bs.readBytes(pmm_data.num_vertices * 3)
    # print("[PMM:Data:UV] File Position: " + hex(bs.tell()))
    pmm_data.uv_bytes = bs.readBytes(pmm_data.num_vertices * 8)
    # print("[PMM:Data:Tri] File Position: " + hex(bs.tell()))
    pmm_data.tri_indices = bs.readBytes(pmm_data.num_tris * 2)
    # print("[PMM:Data:Bone Weights] File Position: " + hex(bs.tell()))
    pmm_data.bone_indices = bs.readBytes(pmm_data.num_vertices)

    return pmm_data


class PmmData:
    """
    Contains data stored in a Summoners War PMM chunk.
    :cvar num_tris: Number of tris in the model. Stored in file as ushort.
    :cvar num_vertices: Number of vertices in the model. Stored in file as ushort.
    :cvar scale_divider: Value to divide position_bytes data by. Stored in file as ushort.
    :cvar position_bytes: Vertex position data. Stored in file as 3x int per item.
    :cvar normal_bytes: Normal data. Stored in file as 3x signed bytes per item.
    :cvar uv_bytes: UV position data. Stored in file as 2x int per item.
    :cvar tri_indices: Triangle data. Stored in file as 3x ushort per item.
    :cvar bone_indices: Weights data. Stored in file as 1 ubyte per item. Index: vert index, value: bone index.
    """

    num_tris = 0
    num_vertices = 0
    scale_divider = 0
    position_bytes = []
    normal_bytes = []
    uv_bytes = []
    tri_indices = []
    bone_indices = []
    material_names = []

    def add_material(self, mat_name):
        self.material_names.append(mat_name)

    def construct_model(self):
        """
        Constructs the model from member properties.
        :rtype: NoeModel
        """
        rapi.rpgCreateContext()
        rapi.rpgBindPositionBuffer(self.position_bytes, noesis.RPGEODATA_INT, 12)
        rapi.rpgSetPosScaleBias(NoeVec3((1 / self.scale_divider, 1 / self.scale_divider, 1 / self.scale_divider)), None)
        rapi.rpgBindNormalBuffer(self.normal_bytes, noesis.RPGEODATA_BYTE, 3)
        rapi.rpgBindUV1Buffer(self.uv_bytes, noesis.RPGEODATA_INT, 8)
        rapi.rpgBindBoneIndexBuffer(self.bone_indices, noesis.RPGEODATA_UBYTE, 1, 1)
        rapi.rpgSetUVScaleBias(NoeVec3((1 / 0xFFFF, -1 / 0xFFFF, 1 / 0xFFFF)), None)

        for material in self.material_names:
            rapi.rpgSetMaterial(material)

        rapi.rpgCommitTriangles(self.tri_indices, noesis.RPGEODATA_USHORT, self.num_tris, noesis.RPGEO_TRIANGLE, 1)
        mdl = rapi.rpgConstructModel()

        return mdl


def bytes_str(bit_array, split=1):
    """
    For debug purposes.
    Returns a clean string representation of the bytes object.
    Example: [0x00, 0xFF, 0x7B] returns "00 FF 7B"
    :param split: Add whitespace after this many bytes
    :type bit_array: bytes | bytearray
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


def pmod_guess_texture_file(filepath):
    filepath = filepath[:-4].rstrip(string.digits) + ".png"
    for _ in range(4):
        if not isfile(filepath):
            filepath = filepath[:-4] + "_water.png"
        if not isfile(filepath):
            filepath = filepath[:-10]
            filepath = filepath[:filepath.rindex("_")] + ".png"
    return filepath
