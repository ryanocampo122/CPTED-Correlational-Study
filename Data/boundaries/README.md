# Boundaries and map context

| File | Contents | Source |
|---|---|---|
| `central_business_district_osm.geojson` | Study-area polygon: the Central Business District neighbourhood (1.20 km²) | OpenStreetMap relation 13754152 (boundary=administrative, admin_level=10), retrieved 16 Oct 2026 |
| `osm_roads_downtown_context.geojson` | Road centrelines around Downtown, used for the maps and by `Scripts/crime_data/hotspots.py` to rebuild the 218 study segments that crime is placed on | OpenStreetMap via Overpass, 16 Oct 2026 |
| `osm_water_downtown_context.geojson` | South Saskatchewan River, clipped to the Downtown map extent, for maps only | OpenStreetMap, 16 Oct 2026 |

The CBD polygon is an **interim** boundary. The work plan specifies the City's neighbourhood boundary; OSM's
admin_level 10 polygons in Saskatoon follow the City's neighbourhoods, but confirm against the City's own file
(open data or through Elisabeth Miller) and re-run `pilot.py points` if it differs.

Map data © OpenStreetMap contributors, available under the Open Database License (ODbL).
