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
# .DAT is a file format that contains both a PMM and PLM chunk, and one or more textures.
# ----------


def registerNoesisTypes():
    """Register the format in this plugin
    :rtype: int
    """

    handle = noesis.register("Summoners War Skinned Mesh", ".pmod")
    noesis.setHandlerTypeCheck(handle, pmm_check_type)
    noesis.setHandlerLoadModel(handle, load_pmm_from_pmod)
    return 1


PMM_HEADER = 'PMM'
PMM_HEADER_CIPHERED = b'\xA6\x8A\x8A'  # Ciphered PMM%
PMM_V2 = '"'   # 0x22 | First known version
PMM_V3 = '#'   # 0x23 | Same as V2
PMM_V4 = '$'   # 0x24 | 1 more byte after reading scale_divider
PMM_V5 = '%'   # 0x25 | Same as V4
PMM_V6 = '&'   # 0x26 | Same as V4
PMM_V7 = '\''  # 0x27 | Same as V4
PMM_V8 = '('   # 0x28 | Version possibly doesn't exist, including it in this script just in case
PMM_V9 = ')'   # 0x29 | Same as V4

PMM_VERSIONS = (PMM_V2, PMM_V3, PMM_V4, PMM_V5, PMM_V6, PMM_V7, PMM_V8, PMM_V9)


def pmm_check_type(data):
    """
    For use by Noesis.
    :type data: bytes
    :rtype: int
    """

    if len(data) < 8:
        return 0
    bs = NoeBitStream(data)

    pmm_header = bs.readBytes(3)
    pmm_version = bs.readBytes(1)
    print(pmm_header + pmm_version)
    return pmm_check_signature(pmm_header, pmm_version, True)


def pmm_check_signature(pmm_header, pmm_version, allow_cipher):
    """
    Check if the PMM chunk signature matches known signatures.
    :param pmm_header:
    :param pmm_version:
    :type allow_cipher: bool
    :param allow_cipher: Whether to allow a ciphered signature to still pass.
    :return: 1 if signature matches known signature, otherwise 0.
    """

    try:
        valid = pmm_header.decode() == PMM_HEADER
        is_known_version = pmm_version.decode() in PMM_VERSIONS
        if valid and is_known_version:
            return 1
        if valid:
            print('Detected PMM with unknown version: {}'.format(pmm_header.decode() + pmm_version.decode()))
        return 0
    except UnicodeDecodeError:
        try:
            pmm_header = as_deciphered(pmm_header).decode()
            pmm_version = as_deciphered(pmm_version).decode()
        except UnicodeDecodeError:
            return 0
        valid = pmm_header == PMM_HEADER
        is_known_version = pmm_version in PMM_VERSIONS
        if valid and is_known_version:
            if allow_cipher:
                return 1
            print("PMM is ciphered. Ensure PMM is deciphered")
        if valid:
            print('Detected PMM with unknown version (ciphered): {}'.format(pmm_header + pmm_version))
        return 0


def pmm_check_ciphered(pmm_header):
    """
    Check if the PMM chunk signature is ciphered.
    :type pmm_header: bytes
    :rtype: int
    """

    return 1 if pmm_header == PMM_HEADER_CIPHERED else 0


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
            if animations is not None:
                model.setAnims(animations)

    tex_filepath = noesis.getSelectedFile()[:-5] + ".png"
    if not isfile(tex_filepath):
        tex_filepath = pmod_guess_texture_file(tex_filepath)
    if not isfile(tex_filepath):
        print("[ERROR] [Tex] Missing PNG file " + tex_filepath +
              "\nThis script expects .pngs to have identical names or same but ending in \"_water\"" +
              "\nYou will have to find the correct PNG file on your own." +
              "\nIt should already be similarly named to the .pmod file.")
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

    pmm_header = bs.readBytes(3)
    pmm_version = bs.readBytes(1)
    if pmm_check_signature(pmm_header, pmm_version, False) == 0:
        raise Exception("[PMM] Unexpected signature: {}".format(pmm_header + pmm_version))

    pmm_header = pmm_header.decode()
    pmm_version = pmm_version.decode()
    print("[PMM:Signature]: {}{}".format(pmm_header, pmm_version))
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

    unk3 = bs.readBytes(0x36 if pmm_header in (PMM_V3, PMM_V2) else 0x37)
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
    materials = []

    def add_material(self, mat_name):
        self.materials.append(mat_name)

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

        for material in self.materials:
            rapi.rpgSetMaterial(material.name)

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
    test = filepath + ""
    guess_suffixes = ("", "_water", "_fire", "_wind", "_light", "_dark", "_ani")
    try:
        test = test[:-4].rstrip(string.digits) + ".png"
        if isfile(test):
            return test

        test = test[:-4]
        for _ in range(6):
            for suffix in guess_suffixes:
                suffix_test = test + suffix + ".png"
                if isfile(suffix_test):
                    return suffix_test
            test = test[:test.rindex("_")]
        if not isfile(test):
            return filepath
        return test
    except ValueError:
        return filepath


def as_deciphered(ciphered_bytes):
    size = len(ciphered_bytes)
    deciphered = bytearray(size)
    for i in range(size):
        deciphered[i] = pmm_decipher[ciphered_bytes[i]]

    return deciphered


pmm_decipher = bytearray([
    0x2f, 0x7c, 0x47, 0x55, 0x32, 0x77, 0x9f, 0xfb, 0x5b, 0x86, 0xfe, 0xb6, 0x3e, 0x06, 0xf4, 0xc4,  # 00-0F
    0x2e, 0x08, 0x49, 0x11, 0x0e, 0xce, 0x84, 0xd3, 0x7b, 0x18, 0xa6, 0x5c, 0x71, 0x56, 0xe2, 0x3b,  # 10-1F
    0xfd, 0xb3, 0x2b, 0x97, 0x9d, 0xfc, 0xca, 0xba, 0x8e, 0x7e, 0x6f, 0x0f, 0xe8, 0xbb, 0xc7, 0xc2,  # 20-2F
    0xd9, 0xa4, 0xd2, 0xe0, 0xa5, 0x95, 0xee, 0xab, 0xf3, 0xe4, 0xcb, 0x63, 0x25, 0x70, 0x4e, 0x8d,  # 30-3F
    0x21, 0x37, 0x9a, 0xb0, 0xbc, 0xc6, 0x48, 0x3f, 0x23, 0x80, 0x20, 0x01, 0xd7, 0xf9, 0x5e, 0xec,  # 40-4F
    0x16, 0xd6, 0xd4, 0x1f, 0x51, 0x42, 0x6c, 0x10, 0x14, 0xb7, 0xcc, 0x82, 0x7f, 0x13, 0x02, 0x00,  # 50-5F
    0x72, 0xed, 0x90, 0x57, 0xc1, 0x2c, 0x5d, 0x28, 0x81, 0x1d, 0x38, 0x1a, 0xac, 0xad, 0x35, 0x78,  # 60-6F
    0xdc, 0x68, 0xb9, 0x8b, 0x6a, 0xe1, 0xc3, 0xe3, 0xdb, 0x6d, 0x04, 0x27, 0x9c, 0x64, 0x5a, 0x8f,  # 70-7F
    0x83, 0x0c, 0xd8, 0xa8, 0x1c, 0x89, 0xd5, 0x43, 0x74, 0x73, 0x4d, 0xae, 0xea, 0x31, 0x6e, 0x1e,  # 80-8F
    0x91, 0x1b, 0x59, 0xc9, 0xbd, 0xf7, 0x07, 0xe7, 0x8a, 0x05, 0x8c, 0x4c, 0xbe, 0xc5, 0xdf, 0xe5,  # 90-9F
    0xf5, 0x2d, 0x4b, 0x76, 0x66, 0xf2, 0x50, 0xd0, 0xb4, 0x85, 0xef, 0xb5, 0x3c, 0x7d, 0x3d, 0xe6,  # A0-AF
    0x9b, 0x03, 0x0d, 0x61, 0x33, 0xf1, 0x92, 0x53, 0xff, 0x96, 0x09, 0x67, 0x69, 0x44, 0xa3, 0x4a,  # B0-BF
    0xaf, 0x41, 0xda, 0x54, 0x46, 0xd1, 0xfa, 0xcd, 0x24, 0xaa, 0x88, 0xa7, 0x19, 0xde, 0x40, 0xeb,  # C0-CF
    0x94, 0x5f, 0x45, 0x65, 0xf0, 0xb8, 0x34, 0xdd, 0x0b, 0xb1, 0x29, 0xe9, 0x2a, 0x75, 0x87, 0x39,  # D0-DF
    0xcf, 0x79, 0x93, 0xa1, 0xb2, 0x30, 0x15, 0x7a, 0x52, 0x12, 0x62, 0x36, 0xbf, 0x22, 0x4f, 0xc0,  # E0-EF
    0xa2, 0x17, 0xc8, 0x99, 0x3a, 0x60, 0xa9, 0xa0, 0x58, 0xf6, 0x0a, 0x9e, 0xf8, 0x6b, 0x26, 0x98   # F0-FF
])