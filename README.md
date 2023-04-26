# noesis-smon
[Noesis](https://richwhitehouse.com/index.php?content=inc_projects.php&showproject=91) plugins that imports [Summoners War: Sky Arena](https://summonerswar.com/en/skyarena) models

---

### This repository hosts the following files:

[fmt_smon_dat](fmt_smon_dat.py): Opens .dat character files, uses fmt_smon_pmm, fmt_smon_plm, and fmt_smon_joker

[fmt_smon_pmm](fmt_smon_pmm.py): Chunk data for skinned meshes. Also opens .pmod files.

[fmt_smon_plm](fmt_smon_plm.py): Chunk data for bones and animations. Opens .pliv files when opening a .pmod file with the same name. pliv files are not opened directly.

[fmt_smon_fid](fmt_smon_fid.py): Opens .fid model files, has no animations.

[fmt_smon_joker](fmt_smon_joker.py): Chunk data for up to two JPEG images: the first a diffuse texture, the second an alpha texture if present.

---

### These plugins allow for opening the following:

**.dat**: Character file, includes a skinned mesh, animations, and textures.
- These are used for monsters, costumes, mounts.

**.pmod**: Contains a skinned mesh. A **.pliv** file with the same name contains the animations.
- These are used for moving buildings, environments, some intro features.

**.pliv**: Not opened directly. Instead, use the **.pmod** file with the same name.

**.fid**: Static mesh file, does not include animations.
- These are used for buildings, terrain.

**.png**: Some PNG files not in PNG format, but instead the proprietary "Joker" format listed above.
