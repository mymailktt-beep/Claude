# Rigging the dealer

`assets/dealer-woman.glb` started as a static, unrigged model. These scripts give it a skeleton the 3D table's arm IK can drive.

1. `node rig.mjs woman.glb woman-rigged.glb`
   - Fits a Mixamo-style skeleton (spine, arms, all five fingers) to her A-pose from the mesh itself: wrist at the arm's narrowest point, elbow 56% of the way down, finger chains from the hand's vertex layout.
   - Writes skin weights.
   - Pushes the sleeve area out a few millimetres.
   - Lists the sleeve and torso UV triangles.
2. `python3 finish.py woman-rigged.glb dealer-woman.glb` paints the white long-sleeve blouse and shrinks the textures.
3. `gltf-transform prune` and `gltf-transform quantize` finish the file.

Needs `@gltf-transform/core` and `@gltf-transform/extensions` (npm), Pillow (pip), and `tools/shrink_glb_textures.py`.
