from inc_noesis import *
from inc_smon import access_bit
from math import ceil


# ----------
# PLM is a chunk containing bone and animation data for a skinned mesh
# The skinned mesh is separately contained in a PMM chunk.
#
# .PMOD is a file format that contains only a PMM chunk.
# .PLIV is a file format that contains only a PLM chunk.
# .DAT is a file format that contains both a PMM and PLM chunk, and one or more textures.
# ----------


# Not registered. To access this file, open the .pmod file with the same name.
# May consider registering it as a type just to make the double click act like opening the .pmod

def registerNoesisTypes():
    """Register the format in this plugin.

    Noesis does not support loading standalone animation files."""

    # handle = noesis.register("Summoners War Skinned Mesh Animation", ".pliv")
    # noesis.setHandlerTypeCheck(handle, plm_check_type)
    # noesis.setHandlerLoadAnim(handle, load_plm)

    handle_tool_1 = noesis.registerTool("Animation ignore scale", plm_tool_ignore_scale,
                                        "When enabled, scale values in file will be ignored when reading animations. " +
                                        "When disabled, scale values in file will be applied to animations.")

    handle_tool_2 = noesis.registerTool("Animation linear interpolation", plm_tool_use_linear_interpolation,
                                        "When enabled, animation interpolation will be set to Linear. " +
                                        "When disabled, animation interpolation will be set to Nearest."
                                        )
    handle_tool_3 = noesis.registerTool("Skip Animations", plm_tool_skip_animations,
                                        "When enabled, animations will not be processed. " +
                                        "When disabled, animations will be processed and applied to the model."
                                        )

    noesis.setToolSubMenuName(handle_tool_1, "Summoners War: Sky Arena")
    noesis.setToolSubMenuName(handle_tool_2, "Summoners War: Sky Arena")
    noesis.setToolSubMenuName(handle_tool_3, "Summoners War: Sky Arena")

    return 0


PLM_SIGNATURE = 'PLM'
PLM_V2 = '"'   # 0x22 | No scale data, transform values are Int32s that get upscaled
PLM_V3 = '#'   # 0x23 | Has scale, extra 2 bytes after reading num_bones
PLM_V4 = '$'   # 0x24 | Same as V3
PLM_V5 = '%'   # 0x25 | Extra 9 bytes after reading num_bones
PLM_V6 = '&'   # 0x26 | Same as V5
PLM_V7 = '\''  # 0x27 | Transform values are now floating point values, scale_divider is unused
PLM_V8 = '('   # 0x28 | Version possibly doesn't exist, including it in this script just in case
PLM_V9 = ')'   # 0x29 | Same as V7

PLM_VERSIONS = (PLM_V2, PLM_V3, PLM_V4, PLM_V5, PLM_V6, PLM_V7, PLM_V8, PLM_V9)

PLM_IGNORE_SCALE = 0
PLM_INTERPOLATE_TYPE = noesis.NOEKF_INTERPOLATE_NEAREST
PLM_IGNORE_ANIMATIONS = 0


def has_scale(v): return v != PLM_V2
def is_floats(v): return v in (PLM_V7, PLM_V8, PLM_V9)


def plm_check_type(data):
    """
    For use by Noesis.
    :type data: bytes
    :rtype: int
    """

    if len(data) < 8:
        return 0
    bs = NoeBitStream(data)

    plm_signature = bs.readBytes(3).decode()
    return 1 if plm_signature == PLM_SIGNATURE else 0


def plm_tool_ignore_scale(handle):
    global PLM_IGNORE_SCALE
    PLM_IGNORE_SCALE = 1 if not PLM_IGNORE_SCALE else 0
    noesis.checkToolMenuItem(handle, PLM_IGNORE_SCALE)
    return PLM_IGNORE_SCALE


def plm_tool_use_linear_interpolation(handle):
    global PLM_INTERPOLATE_TYPE
    if PLM_INTERPOLATE_TYPE != noesis.NOEKF_INTERPOLATE_NEAREST:
        PLM_INTERPOLATE_TYPE = noesis.NOEKF_INTERPOLATE_NEAREST
    else:
        PLM_INTERPOLATE_TYPE = noesis.NOEKF_INTERPOLATE_LINEAR
    noesis.checkToolMenuItem(handle, PLM_INTERPOLATE_TYPE == noesis.NOEKF_INTERPOLATE_LINEAR)
    return PLM_INTERPOLATE_TYPE == noesis.NOEKF_INTERPOLATE_LINEAR


def plm_tool_skip_animations(handle):
    global PLM_IGNORE_ANIMATIONS
    PLM_IGNORE_ANIMATIONS = 1 if not PLM_IGNORE_ANIMATIONS else 0
    noesis.checkToolMenuItem(handle, PLM_IGNORE_ANIMATIONS)
    return PLM_IGNORE_ANIMATIONS


def load_plm_animation(bs, scale_divider):
    """
    Processes the PLM chunk and returns its data.
    :type bs: NoeBitStream
    :param scale_divider: Value from PMM chunk.
    :type scale_divider: int
    :rtype: tuple[list[NoeBone], list[NoeKeyFramedAnim]]
    """
    plm_signature = bs.readBytes(3).decode()
    if plm_signature != PLM_SIGNATURE:
        raise Exception("[PLM] Unexpected signature: {0}".format(plm_signature))

    version = bs.readBytes(1).decode()
    if version not in PLM_VERSIONS:
        raise Exception("[PLM] Unexpected PLM version: {0}".format(version))

    if is_floats(version):
        scale_divider = 1

    print("[PLM:Signature] {}{}".format(plm_signature, version))

    # 2 byte int: number of animations
    num_animations = bs.readUShort()

    # 0x14 bytes unknown data, seems to always be 0x00 x14
    unk1 = bs.readBytes(0x14)
    if any(unk1):
        # print("[PLM:Header:Unk1] (normally all 0x00): {0}".format(bytes_str(unk1)))
        pass

    # for num_animations: 0x5 bytes unknown, 2 byte number of frames in animation
    anim_num_frames = []
    for x in range(num_animations):
        unk_track = bs.readBytes(0x05)
        # print("[PLM:Header:Track{0:02}:Unk] {1}".format(x, bytes_str(unk_track)))
        num_frames = bs.readUShort()
        anim_num_frames.append(num_frames)

    bones = []

    # 1 byte number of bones in model skeleton
    num_bones = bs.readUByte()

    # Various bytes unknown, size dependent on signature
    # print("[PLM:Variable Unknown] File Position: {0}".format(hex(bs.tell())))

    offsets = {
        PLM_V2: 0x06,
        PLM_V3: 0x08,
        PLM_V4: 0x08,
        PLM_V5: 0x11,
        PLM_V6: 0x11,
        PLM_V7: 0x11,
        PLM_V9: 0x11,
    }

    offset = offsets.get(version, 0x11)
    unk2 = bs.readBytes(offset)
    unk3 = bs.readBytes(0x18)

    # print("[PLM:Header:Unk2] {0}".format(bytes_str(unk2)))
    # print("[PLM:Header:Unk3] {0}".format(bytes_str(unk3, 4)))
    # print("[PLM:Bones] File Position: {0}".format(hex(bs.tell())))
    for i in range(num_bones):
        bone = plm_read_bone(bs, scale_divider, version)
        # print("[PLM:Bone{0:03}] Parent: {1}, File Position End: {2}".format(i, bone.parentIndex, hex(bs.tell())))
        bones.append(bone)

    # Bones are stored in local position, we have to apply parent transform
    for i in range(0, num_bones):
        bone = bones[i]
        parent_idx = bones[i].parentIndex
        if parent_idx != 0xFF:
            parent_bone = bones[parent_idx]
            bone.setMatrix(bone.getMatrix() * parent_bone.getMatrix())

    if PLM_IGNORE_ANIMATIONS:
        return bones, None

    kf_animations = plm_read_animations(bs, anim_num_frames, bones, num_animations, num_bones, version,
                                        scale_divider)

    return bones, kf_animations


def plm_read_animations(bs, anim_num_frames, bones, num_animations, num_bones, version, scale_divider):
    kf_animations = []
    # print("[PLM:Tracks] File Position: {0}".format(hex(bs.tell())))
    for x in range(num_animations):
        # print("[PLM:Track{0: 2}] File Position: {1}".format(x, hex(bs.tell())))
        # 0x18 bytes unknown
        unk_track = bs.readBytes(0x18)
        # print("[PLM:Track{0:02}:Unk] {1}".format(x, bytes_str(unk_track, 4)))

        num_frames = anim_num_frames[x]
        # print("[PLM:Track{0: 2}] Frame Count: {1}, File Position: {2}".format(x, num_frames, hex(bs.tell())))
        keyframed_bones = []
        for b in range(num_bones):
            keyframed_bone = plm_read_keyframed_bone_animation(bs, b, num_frames, scale_divider, version)
            keyframed_bones.append(keyframed_bone)
            # print("[PLM:Track{0: 2}:Bone{1: 3}] File Position: {2}".format(x, b, hex(bs.tell())))

        # Note, for .dat files, actual animation names are stored in the game's encrypted infocsv file
        # and are inaccessible here
        animation = NoeKeyFramedAnim("Anim_{0:02}".format(x), bones, keyframed_bones, 60)
        kf_animations.append(animation)
    return kf_animations


def plm_read_bone(bs, scale_divider, version):
    """
    :type bs: NoeBitStream
    :type scale_divider: int
    :param scale_divider: Value from PMM chunk.
    :type version: string
    :param version: PLM version, required to correctly process bone information.
    :rtype: NoeBone
    """

    flag = bs.readUByte()  # Flag is where the game would assign cosmetics, UI features, etc
    bone_id = bs.readUByte()
    parent_id = bs.readUByte()
    next_sibling_id = bs.readUByte()
    first_child_id = bs.readUByte()
    skinned_vert_count = bs.readUShort()

    quaternion = read_quaternion(bs, version)
    translation = read_translation(bs, version) / scale_divider
    scale = read_scale(bs, version)

    bone_matrix = compose_matrix(quaternion, translation, scale)

    print('bone {} parent {} verts {}'.format(bone_id, parent_id, skinned_vert_count))

    return NoeBone(bone_id, "Bone {0}".format(bone_id), bone_matrix, "Bone {0}".format(parent_id), parent_id)


def plm_read_keyframed_bone_animation(bs, bone_id, num_frames, scale_divider, version):
    """
    :type bs: NoeBitStream
    :type bone_id: int
    :type num_frames: int
    :param num_frames: Max number of frames in the track.
    :type scale_divider: int
    :param scale_divider: Value from PMM chunk.
    :type version: string
    :param version: PLM version, required to correctly process bone information.
    :rtype: NoeKeyFramedBone
    """
    interp = PLM_INTERPOLATE_TYPE

    kf_bone = NoeKeyFramedBone(bone_id)
    kf_bone.setRotation(plm_read_keys(bs, num_frames, read_quaternion_key, version),
                        interpolationType=interp)
    kf_bone.setTranslation(plm_read_keys(bs, num_frames, read_translation, version, scale_divider),
                           interpolationType=interp)

    # PLM versions without scale do not have any data here, skip to next bone
    if has_scale(version):
        scale_keys = plm_read_keys(bs, num_frames, read_scale, version)
        if not PLM_IGNORE_SCALE:
            kf_bone.setScale(scale_keys, noesis.NOEKF_SCALE_VECTOR_3)

    return kf_bone


def plm_read_keys(bs, num_frames, read_func, version, scale_divider=1):
    """
    :type bs: NoeBitStream
    :param bs: Bitstream to read the keys from
    :type num_frames: int
    :param num_frames: Maximum number of frames to read
    :type read_func: function
    :param read_func: Function that accepts the NoeBitStream and returns the value used in NoeKeyFramedValue
    :type version: string
    :param version: PLM version, required to correctly process bone information.
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
        output.append(NoeKeyFramedValue(0, read_func(bs, version)))
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
            kf_time = i / 30.0
            if access_bit(key_positions, i):
                val = read_func(bs, version) * (1 / scale_divider)
                kf_value = NoeKeyFramedValue(kf_time, val)
                keys.append(kf_value)
            else:
                # SW Animations likely have no interpolation, not even Nearest.
                if PLM_INTERPOLATE_TYPE != noesis.NOEKF_INTERPOLATE_LINEAR and len(keys) > 0:
                    kf_fake_value = NoeKeyFramedValue(kf_time, keys[-1].value)
                    keys.append(kf_fake_value)

    return keys


def read_quaternion(bs, version):
    """
    Reads a NoeQuat from the bitstream and returns it.
    :type bs: NoeBitStream
    :param bs: Bitstream to read the Quaternion from.
    :type version: string
    :param version: PLM version, required to correctly read quaternion.
    :rtype: NoeQuat
    :return: The NoeQuat read from the stream.
    """
    if is_floats(version):
        # Quaternions are stored as four Float32s
        return NoeQuat.fromBytes(bs.readBytes(16))

    # Quaternions are stored as four Int16s that must be divided by 0x7FFF.
    x, y, z, w = bs.readShort(), bs.readShort(), bs.readShort(), bs.readShort()
    return NoeQuat((x, y, z, w)) * (1 / 0x7FFF)


def read_quaternion_key(bs, version):
    """
    Reads a NoeQuat from the bitstream and returns it.
    This version of the method flips the W component before returning it.
    :type bs: NoeBitStream
    :param bs: Bitstream to read the Quaternion from.
    :type version: string
    :param version: PLM version, required to correctly read quaternion.
    :rtype: NoeQuat
    :return: The NoeQuat read from the stream, with negated W component.
    """
    # This second method exists because *apparently* the quaternion keyframe values' W component is negative
    quaternion = read_quaternion(bs, version)
    quaternion[3] = -quaternion[3]
    return quaternion


def read_translation(bs, version):
    """
    Reads a NoeVec3 from the bitstream and returns it.
    Translations are stored as three integer values.
    As such, NoeVec3.fromBytes() cannot be used, as it expects floating point values.
    :type bs: NoeBitStream
    :param bs: Bitstream to read the Translation Vector3 from.
    :type version: string
    :param version: PLM version, required to correctly read translation.
    :rtype: NoeVec3
    :return: The NoeVec3 representing Translation read from the stream.
    """
    if is_floats(version):
        # Translations are stored as three Float32s
        return NoeVec3.fromBytes(bs.readBytes(12)) * 64

    # Translations are stored as three Int32s
    return NoeVec3((bs.readInt(), bs.readInt(), bs.readInt()))


def read_scale(bs, version):
    """
    Reads a NoeVec3 from the bitstream and returns it.
    Scale values are stored as three integer values that must be divided by 0x10000.
    As such, NoeVec3.fromBytes() cannot be used, as it expects floating point values.
    :type bs: NoeBitStream
    :param bs: Bitstream to read the Scale Vector3 from.
    :type version: string
    :param version: PLM version, required to correctly read scale.
    :rtype: NoeVec3
    :return: The NoeVec3 representing Scale read from the stream.
    """
    # Scales are stored in file as three integer values that must be divided
    # Cannot use NoeVec3.fromBytes() since it expects floating-point values
    if not has_scale(version):
        # Scales are not stored in the file
        return NoeVec3((1, 1, 1))
    if is_floats(version):
        # Scales are stored as three Float32s
        return NoeVec3.fromBytes(bs.readBytes(12))

    # Scales are stored as three Int32s that must be divided by 0x10000
    return NoeVec3((bs.readInt(), bs.readInt(), bs.readInt())) / 0x10000


def compose_matrix(quaternion, translation, scale):
    """
    Creates a 4x3 Matrix from the provided transform values
    :type quaternion: NoeQuat
    :type translation: NoeVec3
    :type scale: NoeVec3
    :rtype: NoeMat43
    """
    matrix = quaternion.toMat43(transposed=1)
    if not PLM_IGNORE_SCALE:
        matrix[0] *= scale[0]
        matrix[1] *= scale[1]
        matrix[2] *= scale[2]
    matrix[3] = translation
    return matrix
