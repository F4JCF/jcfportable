"""Carte des QSO : page HTML Leaflet ouverte dans le navigateur."""
import html
import json

from jcfportable.config import data_dir
from jcfportable.geo import grid_to_latlon

TEMPLATE = """<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><title>Carte — %(title)s</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>html,body,#map{height:100%%;margin:0;font-family:sans-serif}
#t{position:absolute;z-index:999;top:10px;left:60px;background:#fff;padding:6px 10px;border-radius:6px;
box-shadow:0 1px 4px rgba(0,0,0,.3)}</style></head>
<body><div id="t"><b>%(title)s</b> — %(count)s QSO localisés</div><div id="map"></div>
<script>
const me = %(me)s, qsos = %(qsos)s;
const map = L.map('map');
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
  {maxZoom: 18, attribution: '&copy; OpenStreetMap'}).addTo(map);
const pts = [];
if (me) { L.circleMarker(me, {radius: 9, color: '#c0392b', fillOpacity: .9}).addTo(map).bindPopup('Ma station'); pts.push(me); }
for (const q of qsos) {
  L.circleMarker([q.lat, q.lon], {radius: 6, color: '#2471a3', fillOpacity: .8}).addTo(map).bindPopup(q.label);
  if (me) L.polyline([me, [q.lat, q.lon]], {weight: 1, color: '#2471a3', opacity: .5}).addTo(map);
  pts.push([q.lat, q.lon]);
}
if (pts.length > 1) map.fitBounds(pts, {padding: [30, 30]}); else map.setView(pts[0] || [46.5, 2.5], pts.length ? 8 : 5);
</script></body></html>"""


def build_map(op, qsos):
    me = grid_to_latlon(op.get("grid"))
    pts = []
    for q in qsos:
        if q.get("deleted"):
            continue
        ll = grid_to_latlon(q.get("their_grid"))
        if not ll:
            continue
        label = f"<b>{html.escape(q['call'])}</b><br>{html.escape(q.get('name') or '')}<br>" \
                f"{q['start'][11:16]} UTC — {q.get('band') or ''} {q.get('mode') or ''}"
        pts.append({"lat": ll[0], "lon": ll[1], "label": label})
    page = TEMPLATE % {"title": html.escape(op["title"]), "count": len(pts),
                       "me": json.dumps(list(me) if me else None), "qsos": json.dumps(pts)}
    path = data_dir() / f"carte-operation-{op['id']}.html"
    path.write_text(page, encoding="utf-8")
    return path, len(pts)
