# Dealer motion from the reference video

The dealer's animation is measured from the reference gameplay video, not invented.

1. Crop the video to its picture area (it is pillarboxed: 960×720 at x=160 in the 1280×720 frame):
   `ffmpeg -i video.mov -vf "crop=960:720:160:0" vid30/f_%04d.png`
2. `python3 track.py <dir>` runs MediaPipe hand and pose landmarkers on every frame and writes `track.json`.
   It needs the `hand_landmarker.task` and `pose_landmarker_heavy.task` models in `<dir>`.
3. `python3 paths.py <dir>` keeps only the dealer's hands (the ones over the felt) and labels them left and right by continuity.
   It projects each palm and fingertip onto the table through the camera fitted to the video (`tools/fit_camera_to_reference.js`, 1.5 px RMS),
   and writes `paths.json`: each hand's path in table coordinates over time.
4. `node film_round.js <outdir> '["10","6","5","9","K"]' <seconds>` films a stacked round of the game with a frozen,
   stepped clock (one frame per 100 ms of game time), for a side-by-side comparison with the video's frames.

What the measurements set in the game (`integrations/blackjack-table3d.html`):

| Measurement | Value from the video | Where it is used |
|---|---|---|
| Left hand | rests on the shoe; leaves only to square up the hole card and for insurance | `REST.L` |
| Right hand | does all dealing, paying and clearing | |
| Card round trip | 0.3 s back to the shoe, 0.5 s out to the spot | `dealOne` |
| Hole card | flipped in the hand: lift, turn over, lay down, about 0.9 s | `revealCard` |
| Clear | your cards (7.5 s), then hers (8.2 s), then the discard holder (9.2 s); about 1.8 s in all | `clearCards` |
| Payout | out over about 0.8 s with a forward lean, held about 0.4 s at the bet, then back | `queueChip` |
| Dealer's cards | in front of the rack at (−0.03, 0.48) | `DEALER_SPOT` |
| Rack | 0.47 m wide, front edge 0.42 m out | the rack block |
| Shoe mouth | (0.43, 0.32) | `SHOE_POS` |
