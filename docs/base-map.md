# The painted base map

The atlas background is a painted illustration (AI-generated; the map shows a visible mark saying so). Paintings do not follow a map projection, so it was fitted to the atlas's real projection before use.

## How it was fitted

The current painting (wide, 2.3:1, no labels) has no city dots, so the fit uses shape alone:

1. **Ukraine on the painting.** The cream land inside the red border was segmented into a mask.
2. **First fit.** An affine transform matched the mask's centre and spread to the true outline of Ukraine (Natural Earth, drawn through the atlas projection in `frontend/src/features/atlas/projection.ts`).
3. **Refinement.** The painted border was matched to the true border point by point (iterative closest point), then a smooth thin-plate spline warp corrected what an affine transform cannot.

## Result

| Check | Value (atlas units; Ukraine is about 1330 wide) |
| --- | --- |
| Border, median distance | about 3 |
| Border, 90th percentile | about 13 (mostly the Black Sea coast) |

The painting is decoration. City labels, study boxes, pins and place outlines are drawn from true coordinates on top of it, so no result depends on the painting.

## Screen window

The map shows atlas units x −40 to 1680, y 30 to 860 (`ATLAS_VIEW`), wider than the 1600 × 1000 projection box, so the painted neighbours fill wide screens. The projection itself is unchanged.

## Files

- `frontend/src/features/atlas/assets/painted-base.webp`: the warped painting, exactly covering `ATLAS_VIEW`.
