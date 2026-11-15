# The painted base map

The atlas background is a painted illustration (AI-generated; the map shows a visible mark saying so). Paintings do not follow a map projection, so it was fitted to the atlas's real projection before use.

## How it was fitted

1. **Control points.** The six city dots on the painting (Kyiv, Lviv, Odesa, Kharkiv, Dnipro, Donetsk) were located automatically and matched to their true positions in the atlas projection (Lambert conformal conic, `frontend/src/features/atlas/projection.ts`).
2. **First fit.** An affine transform from the six pairs left city errors of 5–15 atlas units (of 1600).
3. **Border fit.** The painted red border and coastline were matched to the true Natural Earth outline of Ukraine, about every 12 units, and a smooth thin-plate spline warp was fitted to those offsets and the cities.

## Result

| Check | Value (atlas units, map is 1600 wide) |
| --- | --- |
| City dots after the warp | within 3 units of true positions |
| Border, median distance | about 5 |
| Border, 90th percentile | about 18 (mostly the Black Sea coast and Crimea, which the painting simplifies) |

The painting is decoration. Study boxes, pins and place outlines are drawn from true coordinates on top of it, so no result depends on the painting.

## Files

- `frontend/src/features/atlas/assets/painted-base.webp`: the warped painting with soft transparent edges.
- Beyond the painting's edges the vector geography (Natural Earth) shows through in a matching parchment tone.
