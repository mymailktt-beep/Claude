# Integrations

## `blackjack-dealer3d.html`

The snippet that puts `assets/dealer.glb` into the BlackJack artifact in place of the dealer sprite. Paste it just before `</body>`, then replace `__GLB__` with the base64 of `assets/dealer.glb`.

What it does:
- Renders the 3D dealer, head and body, inside the existing `#bjDealer` portrait box, with the same framing as the sprite. The model's own arms are hidden because the game's 2D arms deal the cards.
- Plays `Idle` all the time. While a card is being dealt, his head follows the dealing hand. When a hand settles, he plays `Nod`.
- If WebGL or three.js can't load, the original sprite stays.

The game's `bjDealerPose()` also needs two changes: it keeps the `d3` class and calls `window.__d3pose(name, ms)`. That way the existing `dl_aim` and `dl_complete` calls drive the 3D dealer.
