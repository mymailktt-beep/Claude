# Integrations

## `blackjack-table3d.html` (current)

Turns the BlackJack artifact into a full 3D table: casino carpet, blue felt with the printed arcs and betting circles, a leather and burl-wood rail with gold cup holders, a chip rack, an acrylic shoe, a discard holder, a limits placard and leather chairs. The dealer from `assets/dealer.glb` stands behind the table and deals every card with his own left hand from the shoe, using two-bone IK for the arms.

![3D table](../assets/table3d-preview.png)

How it fits into the game:
- It reads the game state (`S.hands`, `S.dealer`, `S.phase`, `S.bet`) every frame and mirrors it. Cards, chip stacks, totals and outcomes follow the game, and the rules code is untouched.
- It hides the 2D table layers by adding the `w3d` class to `#wrap`. The page needs the CSS block that goes with that class. The buttons, chip tray, banner and menu stay as they are.
- A camera button in the top bar cycles between your seat and the two side views.
- If WebGL or three.js can't load, the 2D table stays.

To install it, paste the snippet before `</body>` and replace `__GLB__` with the base64 of `assets/dealer.glb`.


## `blackjack-dealer3d.html` (earlier, superseded)

The snippet that puts `assets/dealer.glb` into the BlackJack artifact in place of the dealer sprite. Paste it just before `</body>`, then replace `__GLB__` with the base64 of `assets/dealer.glb`.

What it does:
- Renders the 3D dealer, head and body, inside the existing `#bjDealer` portrait box, with the same framing as the sprite. The model's own arms are hidden because the game's 2D arms deal the cards.
- Plays `Idle` all the time. While a card is being dealt, his head follows the dealing hand. When a hand settles, he plays `Nod`.
- If WebGL or three.js can't load, the original sprite stays.

The game's `bjDealerPose()` also needs two changes: it keeps the `d3` class and calls `window.__d3pose(name, ms)`. That way the existing `dl_aim` and `dl_complete` calls drive the 3D dealer.
