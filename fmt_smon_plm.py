from inc_noesis import *
from math import ceil

# ----------
# PLM is a chunk containing bone and animation data for a skinned mesh
# The skinned mesh is separately contained in a PMM chunk.
#
# .PMOD is a file format that contains only a PMM chunk.
# .PLIV is a file format that contains only a PLM chunk.
# .DAT is a file format that contains both a PMM and PLM chunk, and textures.
# ----------


# Not registered. To access this file, open the .pmod file with the same name.
# May consider registering it as a type just to make the double click act like opening the .pmod

# def registerNoesisTypes():
#     """Register the format in this plugin.
#
#     Noesis does not support loading standalone animation files."""
#
#     handle = noesis.register("Summoners War Skinned Mesh Animation", ".pliv")
#     noesis.setHandlerTypeCheck(handle, plm_check_type)
#     noesis.setHandlerLoadAnim(handle, load_plm)
#     return 0


PLM_HEADER_V1 = 'PLM$'
PLM_HEADER_V2 = 'PLM#'  # No apparent changes from V1
PLM_HEADER_V3 = 'PLM%'  # Extra 9 bytes after reading num_bones
PLM_HEADER_V4 = 'PLM"'  # Contains no scale information, less bytes after num_bones
PLM_HEADERS = (PLM_HEADER_V1, PLM_HEADER_V2, PLM_HEADER_V3, PLM_HEADER_V4)


def plm_check_type(data):
    """
    For use by Noesis.
    :type data: bytes
    :rtype: int
    """

    if len(data) < 8:
        return 0
    bs = NoeBitStream(data)

    plm = bs.readBytes(4).decode()
    return 1 if plm in PLM_HEADERS else 0


def load_plm_animation(bs, scale_divider):
    """
    Processes the PLM chunk and returns its data.
    :type bs: NoeBitStream
    :param scale_divider: Value from PMM chunk.
    :type scale_divider: int
    :rtype: tuple[list[NoeBone], list[NoeKeyFramedAnim]]
    """
    plm_signature = bs.readBytes(4).decode()
    if plm_signature not in PLM_HEADERS:
        raise Exception("[PLM] Unexpected signature: {0}".format(plm_signature))

    print("[PLM:Signature] {0}".format(plm_signature))

    # 2 byte int: number of animations
    num_anim = bs.readUShort()

    # 0x14 bytes unknown data, seems to always be 0x00 x14
    unk1 = bs.readBytes(0x14)
    if any(unk1):
        # print("[PLM:Header:Unk1] (normally all 0x00): {0}".format(bytes_str(unk1)))
        pass

    # for num_anim: 0x5 bytes unknown, 2 byte number of frames in animation
    anim_num_frames = []
    for x in range(num_anim):
        unk_track = bs.readBytes(0x05)
        # print("[PLM:Header:Track{0:02}:Unk] {1}".format(x, bytes_str(unk_track)))
        num_frames = bs.readUShort()
        anim_num_frames.append(num_frames)

    bones = []

    # 2 bytes number of bones in model skeleton
    num_bones = bs.readUByte()

    # Various bytes unknown, size dependent on signature
    if plm_signature == PLM_HEADER_V3:
        unk2 = bs.readBytes(0x11)
    elif plm_signature == PLM_HEADER_V4:
        unk2 = bs.readBytes(0x6)
    else:
        unk2 = bs.readBytes(0x8)
    unk3 = bs.readBytes(0x18)

    # print("[PLM:Header:Unk2] {0}".format(bytes_str(unk2)))
    # print("[PLM:Header:Unk3] {0}".format(bytes_str(unk3, 4)))
    # print("[PLM:Bones] File Position: {0}".format(hex(bs.tell())))
    for i in range(num_bones):
        bone = plm_read_bone(bs, scale_divider, plm_signature)
        # print("[PLM:Bone{0:03}] Parent: {1}, File Position End: {2}".format(i, bone.parentIndex, hex(bs.tell())))
        bones.append(bone)

    # Bones are stored in local position, we have to apply parent transform
    for i in range(0, num_bones):
        bone = bones[i]
        parent_idx = bones[i].parentIndex
        if parent_idx != -1:
            parent_bone = bones[parent_idx]
            bone.setMatrix(bone.getMatrix() * parent_bone.getMatrix())

    kf_animations = []
    # print("[PLM:Tracks] File Position: {0}".format(hex(bs.tell())))
    for x in range(num_anim):
        # print("[PLM:Track{0: 2}] File Position: {1}".format(x, hex(bs.tell())))
        # 0x18 bytes unknown
        unk_track = bs.readBytes(0x18)
        # print("[PLM:Track{0:02}:Unk] {1}".format(x, bytes_str(unk_track, 4)))

        num_frames = anim_num_frames[x]
        # print("[PLM:Track{0: 2}] Frame Count: {1}, File Position: {2}".format(x, num_frames, hex(bs.tell())))
        keyframed_bones = []
        for b in range(num_bones):
            keyframed_bone = plm_read_keyframed_bone_animation(bs, b, num_frames, scale_divider, plm_signature)
            keyframed_bones.append(keyframed_bone)
            # print("[PLM:Track{0: 2}:Bone{1: 3}] File Position: {2}".format(x, b, hex(bs.tell())))

        # Note, for .dat files, actual animation names are stored in the game's encrypted infocsv file
        # and are inaccessible here
        animation = NoeKeyFramedAnim("Anim_{0:02}".format(x), bones, keyframed_bones, 60)
        kf_animations.append(animation)

    return bones, kf_animations


def plm_read_bone(bs, scale_divider, plm_signature):
    """
    :type bs: NoeBitStream
    :type scale_divider: int
    :param scale_divider: Value from PMM chunk.
    :type plm_signature: string
    :param plm_signature: PLM chunk signature values, required to correctly process bone information.
    :rtype: NoeBone
    """
    # 1 byte in-game flag (where the game would assign cosmetics, UI features, etc)
    flag = bs.readUByte()

    # 1 byte bone-id
    bone_id = bs.readUByte()

    # 1 byte id of the parent bone. Value is 0xFF if no parent, set to -1
    parent_id = bs.readUByte()
    if parent_id == 255:
        parent_id = -1

    # 4 bytes unknown
    unk = bs.readBytes(4)
    # print("[PLM:Bone{0: 3}:Unk] {1}".format(bone_id, bytes_str(unk)))

    # 8 bytes quaternion values (4 Int16 values)
    quaternion = read_quaternion(bs)

    # 12 bytes translation values (3 Int32 values)
    translation = read_translation(bs) / scale_divider

    # 12 bytes scale values (3 int32 values)
    # PLM chunks with signature 'PLM"' do not include Scale data
    scale = read_scale(bs) if plm_signature != PLM_HEADER_V4 else NoeVec3((1, 1, 1))

    bone_matrix = quaternion.toMat43(transposed=1)
    bone_matrix[0] *= scale[0]
    bone_matrix[1] *= scale[1]
    bone_matrix[2] *= scale[2]
    bone_matrix[3] = translation

    return NoeBone(bone_id, "Bone {0}".format(bone_id), bone_matrix, "Bone {0}".format(parent_id), parent_id)


def plm_read_keyframed_bone_animation(bs, bone_id, num_frames, scale_divider, plm_signature):
    """
    :type bs: NoeBitStream
    :type bone_id: int
    :type num_frames: int
    :param num_frames: Max number of frames in the track.
    :type scale_divider: int
    :param scale_divider: Value from PMM chunk.
    :type plm_signature: string
    :param plm_signature: PLM chunk signature values, required to correctly process bone information.
    :rtype: NoeKeyFramedBone
    """
    kf_bone = NoeKeyFramedBone(bone_id)
    kf_bone.setRotation(plm_read_keys(bs, num_frames, read_quaternion_2))
    kf_bone.setTranslation(plm_read_keys(bs, num_frames, read_translation, scale_divider))
    # PLM chunks with signature 'PLM"' do not include Scale data
    if plm_signature != PLM_HEADER_V4:
        kf_bone.setScale(plm_read_keys(bs, num_frames, read_scale), noesis.NOEKF_SCALE_VECTOR_3)

    return kf_bone


def plm_read_keys(bs, num_frames, read_func, scale_divider=1):
    """
    :type bs: NoeBitStream
    :param bs: Bitstream to read the keys from
    :type num_frames: int
    :param num_frames: Maximum number of frames to read
    :type read_func: function
    :param read_func: Function that accepts the NoeBitStream and returns the value used in NoeKeyFramedValue
    :type scale_divider: float
    :param scale_divider: Value to divide the key value by
    :return: List of NoeKeyFramedValue read from the bitstream
    :rtype: list[NoeKeyFramedValue]
    """
    keys = []
    output = []
    # Test first byte.
    # If non-zero: this byte is part of a bitarray denoting key positions, where sum of On bits is number of keys
    # If zero: this byte denotes that there is only one key (value is the default bone position)
    if bs.readByte() == 0:
        # Value of zero means exactly one key on this bone for this attribute
        output.append(NoeKeyFramedValue(0, read_func(bs)))
    else:
        # Non-zero means this is bitarray of size equal to animation length
        # Example: if animation length is 64-71, that's 64-71 bits or 9 bytes
        # Number of bytes is rounded up with an extra bit, bits equal to exactly x bytes is treated as x+1 bytes.
        # Example: 64 bits is treated as 9 bytes, 72 as 10, 80 as 11.

        bs.seek(-1, NOESEEK_REL)
        key_position_size = int(ceil((num_frames + 1) / 8))
        key_positions = bs.readBytes(key_position_size)

        # Key count is equal to num bits that equal 1
        # Key position is wherever bit equals 1
        # example: if bitarray is 10001011, i would create key at 0, 4, 6, 7
        for i in range(num_frames):
            if access_bit(key_positions, i):
                val = read_func(bs) * (1 / scale_divider)
                kf_value = NoeKeyFramedValue(i / 30.0, val)
                keys.append(kf_value)

    return keys


def read_quaternion(bs):
    """
    Reads a NoeQuat from the bitstream and returns it.
    Quaternions are stored as four 2-byte shorts that must be divided by 0x7FFF.
    As such, NoeQuat.fromBytes cannot be used.
    :type bs: NoeBitStream
    :param bs: Bitstream to read the Quaternion from.
    :rtype: NoeQuat
    :return: The NoeQuat read from the stream.
    """

    # Quaternions are stored in file as four 2-byte short values that must be divided
    # Cannot use NoeQuat.fromBytes() since it expects 4-byte values
    # NoeQuat not divisible, must be multiplied by divided value
    x, y, z, w = bs.readShort(), bs.readShort(), bs.readShort(), bs.readShort()
    return NoeQuat((x, y, z, w)) * (1 / 0x7FFF)


def read_quaternion_2(bs):
    """
    Reads a NoeQuat from the bitstream and returns it.
    Quaternions are stored as four 2-byte shorts that must be divided by 0x7FFF.
    As such, NoeQuat.fromBytes cannot be used, as it expects 4-byte floating-point values.
    This version of the method negates the W component before returning it.
    :type bs: NoeBitStream
    :param bs: Bitstream to read the Quaternion from.
    :rtype: NoeQuat
    :return: The NoeQuat read from the stream, with negated W component.
    """
    # Quaternions are stored in file as four 2-byte short values that must be divided
    # Cannot use NoeQuat.fromBytes() since it expects 4-byte values
    # NoeQuat not divisible, must be multiplied by divided value
    # This second method exists because *apparently* the quaternion keyframe values' W component is negative
    quat = read_quaternion(bs)
    quat[3] = -quat[3]
    return quat


def read_translation(bs):
    """
    Reads a NoeVec3 from the bitstream and returns it.
    Translations are stored as three integer values.
    As such, NoeVec3.fromBytes() cannot be used, as it expects floating point values.
    :type bs: NoeBitStream
    :param bs: Bitstream to read the Translation Vector3 from.
    :rtype: NoeVec3
    :return: The NoeVec3 representing Translation read from the stream.
    """
    # Translations are stored in file as three integer values
    # Cannot use NoeVec3.fromBytes() since it expects floating-point values
    return NoeVec3((bs.readInt(), bs.readInt(), bs.readInt()))


def read_scale(bs):
    """
    Reads a NoeVec3 from the bitstream and returns it.
    Scale values are stored as three integer values that must be divided by 0x10000.
    As such, NoeVec3.fromBytes() cannot be used, as it expects floating point values.
    :type bs: NoeBitStream
    :param bs: Bitstream to read the Scale Vector3 from.
    :rtype: NoeVec3
    :return: The NoeVec3 representing Scale read from the stream.
    """
    # Scales are stored in file as three integer values that must be divided
    # Cannot use NoeVec3.fromBytes() since it expects floating-point values
    return NoeVec3((bs.readInt(), bs.readInt(), bs.readInt())) / 0x10000


def access_bit(data, index):
    """
    Returns the bit value at the provided index
    :type data: bytearray
    :type index: int
    :rtype: int
    """
    base = int(index // 8)
    shift = int(index % 8)
    return (data[base] >> shift) & 0x1


def bytes_str(bit_array, split=1):
    """
    Returns a clean string representation of the bytes object
    Example: [0x00, 0xFF, 0x7B] returns "00 FF 7B"
    :param split: Add whitespace after this many bytes
    :type bit_array: bytearray | bytes
    :param bit_array: The bytes to get a string representation from
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
