"""Rebuild src/features/atlas/geo/atlas-geo.json from Natural Earth 1:10m (public domain).

usage: python3 build_geo.py DIR_WITH_NATURAL_EARTH_GEOJSON OUT_JSON

Inputs (github.com/nvkelso/natural-earth-vector, geojson/):
  ne_10m_admin_0_countries_ukr.geojson   Ukraine point of view: Crimea is drawn as part of Ukraine
  ne_10m_rivers_lake_centerlines.geojson

Output: one FeatureCollection. properties.kind is "ukraine", "neighbour" or "river".
Shapes are simplified (Douglas-Peucker) and cut to a box larger than the atlas frame.
Ukraine keeps a ~1 km tolerance, which is far below one screen pixel at atlas scale.
"""
import json
import sys

BBOX = (14.0, 40.0, 48.0, 57.5)  # west, south, east, north: wider than the atlas frame
RIVERS = {'Dnieper', 'Dniester', 'Southern Bug', 'Desna', 'Donets', 'Pripyat', 'Danube', 'Prut', 'Seym', 'Don'}


def simplify(points, tol):
    """Iterative Douglas-Peucker in degrees."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        (x1, y1), (x2, y2) = points[a], points[b]
        dx, dy = x2 - x1, y2 - y1
        norm = (dx * dx + dy * dy) ** 0.5 or 1e-12
        worst, index = 0.0, -1
        for i in range(a + 1, b):
            x, y = points[i]
            dist = abs(dy * (x - x1) - dx * (y - y1)) / norm if norm > 1e-12 else ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
            if dist > worst:
                worst, index = dist, i
        if worst > tol and index > 0:
            keep[index] = True
            stack += [(a, index), (index, b)]
    return [p for p, k in zip(points, keep) if k]


def inside(ring):
    w, s, e, n = BBOX
    return any(w <= x <= e and s <= y <= n for x, y in ring)


def clamp(ring):
    """Vertices outside the box are pulled onto its edge. The edge is off-frame, so this is never visible."""
    w, s, e, n = BBOX
    out = []
    for x, y in ring:
        p = [round(min(max(x, w), e), 3), round(min(max(y, s), n), 3)]
        if not out or out[-1] != p:
            out.append(p)
    return out


def ring_area(ring):
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:]))) / 2


def main(src, out_path):
    features = []
    countries = json.load(open(f'{src}/ne_10m_admin_0_countries_ukr.geojson'))
    for feature in countries['features']:
        name = feature['properties']['ADMIN']
        geom = feature['geometry']
        polys = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]
        is_ukraine = name == 'Ukraine'
        tol = 0.008 if is_ukraine else 0.03
        kept = []
        for poly in polys:
            outer = [(c[0], c[1]) for c in poly[0]]
            if not inside(outer):
                continue
            ring = clamp(simplify(outer, tol))
            if len(ring) >= 4 and ring_area(ring) > (0.0005 if is_ukraine else 0.01):
                if ring[0] != ring[-1]:
                    ring.append(ring[0])
                kept.append([ring])
        if kept:
            features.append({'type': 'Feature', 'properties': {'kind': 'ukraine' if is_ukraine else 'neighbour', 'name': name},
                             'geometry': {'type': 'MultiPolygon', 'coordinates': kept}})

    rivers = json.load(open(f'{src}/ne_10m_rivers_lake_centerlines.geojson'))
    for feature in rivers['features']:
        name = feature['properties'].get('name_en')
        geom = feature['geometry']
        if name not in RIVERS or not geom:
            continue
        lines = geom['coordinates'] if geom['type'] == 'MultiLineString' else [geom['coordinates']]
        kept = []
        for line in lines:
            pts = [(c[0], c[1]) for c in line]
            if inside(pts):
                kept.append([[round(x, 3), round(y, 3)] for x, y in simplify(pts, 0.008)])
        if kept:
            features.append({'type': 'Feature', 'properties': {'kind': 'river', 'name': name},
                             'geometry': {'type': 'MultiLineString', 'coordinates': kept}})

    json.dump({'type': 'FeatureCollection', 'source': 'Natural Earth 1:10m, public domain (Ukraine point-of-view countries file)',
               'features': features}, open(out_path, 'w'), separators=(',', ':'))
    print(len(features), 'features')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
