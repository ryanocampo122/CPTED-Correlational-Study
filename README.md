# CPTED Computer Vision and Correlational Sentiment analysis of Public Safety - A Study on Crime Patterns - Saskatoon

**ComputerVision_Sentinel**, a University of Saskatchewan (AIRI 2026) research project.

## The project

**Research aim:** To examine the correlations between built-environment features of public space in Saskatoon, measured from street-level imagery using computer vision, and (a) crime hotspots and (b) public perceptions of safety expressed on Reddit, using only openly available secondary data. The study is correlational: it identifies associations and spatial patterns rather than testing cause and effect.

**Research questions:**

- **RQ1:** To what extent are CPTED features measured from street-level imagery correlated with the locations of selected crime types?
- **RQ2:** To what extent are the same CPTED features correlated with perceptions of safety expressed on Reddit?
- **RQ3:** How strongly are perceived danger on Reddit and recorded crime correlated across space, and where do they diverge?

The project tests Crime Prevention Through Environmental Design (**CPTED**), the idea that storefronts, windows
overlooking the street, lighting and upkeep discourage crime. Instead of walking the streets with a checklist, it
measures these features from street photos with computer vision, then compares them street by street with police
records and Reddit discussion from summer 2026 (1 June – 31 August).

Three public data sources:

| What is measured | Where it comes from | How |
|---|---|---|
| What the streets look like | street photos on Mapillary | image models measure buildings, trees, sky, street lights, people and signs of disorder in each photo |
| Where crime is recorded | Saskatoon Police Service (SPS) records | each record is placed on the street it names |
| How safe people feel | posts and comments on Reddit's r/saskatoon | posts are tagged by place and scored for tone (negative, neutral, positive) |

<!-- boundary maps: start (written by Scripts/reporting/embed_boundary_maps.py) -->

**Study area: the Central Business District** ([`central_business_district_osm.geojson`](Data/boundaries/central_business_district_osm.geojson))

```geojson
{"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Polygon","coordinates":[[[-106.668757,52.1220542],[-106.668759,52.1222658],[-106.6687635,52.1227122],[-106.6687361,52.1230633],[-106.6688269,52.123471],[-106.6689998,52.1238998],[-106.6692582,52.1243443],[-106.6694893,52.124688],[-106.669782,52.1251934],[-106.6699754,52.1255886],[-106.6701723,52.126094],[-106.6701979,52.1263105],[-106.6702151,52.1269977],[-106.6702202,52.1278636],[-106.6702237,52.1293031],[-106.6702332,52.1304864],[-106.6702366,52.1325395],[-106.6701749,52.1332794],[-106.6696122,52.1333075],[-106.6689312,52.1333588],[-106.6683032,52.1334489],[-106.6673877,52.1336177],[-106.6663246,52.1338729],[-106.666019,52.1339201],[-106.6655226,52.1339348],[-106.6646428,52.1339474],[-106.6644363,52.1339441],[-106.6640403,52.1339369],[-106.6635028,52.1338823],[-106.6628421,52.1337562],[-106.6609969,52.1334284],[-106.6572346,52.1327307],[-106.6533764,52.1320183],[-106.6522262,52.1318061],[-106.6519283,52.1317283],[-106.651562,52.1315959],[-106.6511855,52.1314005],[-106.6504642,52.1310048],[-106.6508007,52.1307411],[-106.6510647,52.1305647],[-106.6512163,52.1304297],[-106.6515265,52.1302771],[-106.6521,52.1300667],[-106.6525205,52.1299976],[-106.6527741,52.1299222],[-106.6529273,52.1298255],[-106.6530039,52.1298259],[-106.6530603,52.1298135],[-106.6530654,52.1297768],[-106.6530986,52.1297425],[-106.653457,52.1295421],[-106.6537132,52.1294704],[-106.6538887,52.1293746],[-106.6541119,52.129301],[-106.6545237,52.1290777],[-106.6548627,52.1288773],[-106.6550892,52.1286024],[-106.6552302,52.1284997],[-106.6555093,52.1285072],[-106.6555658,52.1284745],[-106.6555103,52.1284449],[-106.6552067,52.1284346],[-106.6550172,52.12857],[-106.654787,52.1288003],[-106.6543173,52.1290405],[-106.6540598,52.129185],[-106.6537715,52.1293214],[-106.6537588,52.1293205],[-106.6537521,52.1293115],[-106.6537544,52.1292911],[-106.6537554,52.1292722],[-106.6537718,52.1292571],[-106.6540078,52.1291104],[-106.6543656,52.1287725],[-106.6546906,52.1284861],[-106.6551473,52.1281452],[-106.6554949,52.1279824],[-106.6557703,52.1277537],[-106.6559378,52.1274851],[-106.6564808,52.1267719],[-106.6567309,52.126608],[-106.6568254,52.1264309],[-106.657123,52.1257238],[-106.657364,52.1251796],[-106.6575124,52.1250106],[-106.6591023,52.1237297],[-106.6607163,52.1228253],[-106.6611626,52.1227146],[-106.6622355,52.1225618],[-106.6634028,52.1225407],[-106.6635853,52.1224924],[-106.6637984,52.122446],[-106.6638443,52.1224413],[-106.6638724,52.1224717],[-106.6647844,52.1222263],[-106.6647844,52.1222099],[-106.6648796,52.1221662],[-106.6649477,52.122156],[-106.6650851,52.1221666],[-106.6653168,52.1221982],[-106.6655485,52.1222034],[-106.6662421,52.1221572],[-106.6663427,52.1221992],[-106.666505,52.1221753],[-106.6665313,52.1221469],[-106.6665633,52.122131],[-106.6666386,52.1221244],[-106.6666981,52.1221564],[-106.6671246,52.1221366],[-106.6672346,52.122088],[-106.6674116,52.1220683],[-106.6675913,52.1220664],[-106.6677201,52.1220875],[-106.6678831,52.1221402],[-106.6679317,52.1221739],[-106.6678986,52.1222469],[-106.6678401,52.1223091],[-106.6678576,52.1223594],[-106.6679142,52.1224085],[-106.6679922,52.1224049],[-106.6680019,52.1223451],[-106.6679861,52.1222561],[-106.6680548,52.1221455],[-106.6681492,52.1220822],[-106.6683123,52.1220454],[-106.6684798,52.1220374],[-106.668757,52.1220542]]]},"properties":{"name":"Central Business District","source":"OpenStreetMap relation 13754152 (boundary=administrative, admin_level=10)","license":"ODbL, (c) OpenStreetMap contributors","retrieved":"2026-10-16","note":"Interim study-area boundary. Confirm against the City of Saskatoon's official neighbourhood polygon before final sampling."}}]}
```

<table><tr><td width="50%" valign="top">

**South Saskatchewan River** ([`osm_water_downtown_context.geojson`](Data/boundaries/osm_water_downtown_context.geojson))

```geojson
{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"name":"South Saskatchewan River and other water","source":"OpenStreetMap, ODbL","note":"clipped to the Downtown map extent"},"geometry":{"type":"MultiPolygon","coordinates":[[[[-106.6291295,52.1412266],[-106.6290843,52.1412275],[-106.6290835,52.1412155],[-106.6290393,52.141216],[-106.6290375,52.1412024],[-106.6289977,52.1412035],[-106.6289968,52.1411899],[-106.628957,52.1411905],[-106.6289552,52.1411726],[-106.6289092,52.1411731],[-106.628908,52.141138],[-106.6289703,52.1411204],[-106.629018,52.1410987],[-106.6290499,52.1410819],[-106.6290857,52.1410697],[-106.6291154,52.1410553],[-106.6291373,52.1410344],[-106.629149,52.1410102],[-106.6291454,52.1409794],[-106.6291295,52.1409493],[-106.6291893,52.1409421],[-106.6292563,52.1409582],[-106.6292863,52.1409725],[-106.6293099,52.140996],[-106.6293109,52.141011],[-106.6293083,52.1410308],[-106.6293082,52.1411134],[-106.629323,52.1411315],[-106.6293335,52.1411586],[-106.6293161,52.1412069],[-106.6292898,52.1412346],[-106.6292461,52.1412552],[-106.6291703,52.141257],[-106.6291711,52.1412415],[-106.6291295,52.1412421],[-106.6291295,52.1412266]]],[[[-106.6777674,52.1178059],[-106.6775855,52.1180003],[-106.6775099,52.1182117],[-106.6773684,52.1183154],[-106.6770035,52.1186228],[-106.6767546,52.1189021],[-106.6766859,52.1190128],[-106.676437,52.1191709],[-106.6762654,52.1193448],[-106.676231,52.1194291],[-106.6759736,52.1196663],[-106.6758963,52.1197875],[-106.6758105,52.1198824],[-106.6755272,52.1200299],[-106.67545,52.1201775],[-106.6752011,52.120362],[-106.6749522,52.1204305],[-106.6749436,52.1205569],[-106.6747548,52.1206307],[-106.6747805,52.1206834],[-106.6746603,52.1207256],[-106.6746346,52.1208046],[-106.6742484,52.1209944],[-106.6738879,52.1212737],[-106.6736304,52.121416],[-106.6734186,52.1215015],[-106.6732527,52.1215688],[-106.6730038,52.1216215],[-106.6719479,52.1220489],[-106.6718253,52.122154],[-106.6713756,52.1222418],[-106.6709778,52.1223622],[-106.6704478,52.1223822],[-106.6702339,52.1223766],[-106.6700194,52.1222301],[-106.6699416,52.1221872],[-106.6697914,52.1221658],[-106.6695339,52.1221625],[-106.6694293,52.1220818],[-106.668757,52.1220542],[-106.6684798,52.1220374],[-106.6683123,52.1220454],[-106.6681492,52.1220822],[-106.6680548,52.1221455],[-106.6679861,52.1222561],[-106.6680019,52.1223451],[-106.6679922,52.1224049],[-106.6679142,52.1224085],[-106.6678576,52.1223594],[-106.6678401,52.1223091],[-106.6678986,52.1222469],[-106.6679317,52.1221739],[-106.6678831,52.1221402],[-106.6677201,52.1220875],[-106.6675913,52.1220664],[-106.6674116,52.1220683],[-106.6672346,52.122088],[-106.6671246,52.1221366],[-106.6666981,52.1221564],[-106.6666386,52.1221244],[-106.6665633,52.122131],[-106.6665313,52.1221469],[-106.666505,52.1221753],[-106.6663427,52.1221992],[-106.6662421,52.1221572],[-106.6655485,52.1222034],[-106.6653168,52.1221982],[-106.6650851,52.1221666],[-106.6649477,52.122156],[-106.6648796,52.1221662],[-106.6647844,52.1222099],[-106.6647844,52.1222263],[-106.6638724,52.1224717],[-106.6638443,52.1224413],[-106.6637984,52.122446],[-106.6635853,52.1224924],[-106.6634028,52.1225407],[-106.6622355,52.1225618],[-106.6611626,52.1227146],[-106.6607163,52.1228253],[-106.6591023,52.1237297],[-106.6575124,52.1250106],[-106.657364,52.1251796],[-106.657123,52.1257238],[-106.6568254,52.1264309],[-106.6567309,52.126608],[-106.6564808,52.1267719],[-106.6559378,52.1274851],[-106.6557703,52.1277537],[-106.6554949,52.1279824],[-106.6551473,52.1281452],[-106.6546906,52.1284861],[-106.6543656,52.1287725],[-106.6540078,52.1291104],[-106.6537718,52.1292571],[-106.6537554,52.1292722],[-106.6537544,52.1292911],[-106.6537521,52.1293115],[-106.6537588,52.1293205],[-106.6537715,52.1293214],[-106.6540598,52.129185],[-106.6543173,52.1290405],[-106.654787,52.1288003],[-106.6550172,52.12857],[-106.6552067,52.1284346],[-106.6555103,52.1284449],[-106.6555658,52.1284745],[-106.6555093,52.1285072],[-106.6552302,52.1284997],[-106.6550892,52.1286024],[-106.6548627,52.1288773],[-106.6545237,52.1290777],[-106.6541119,52.129301],[-106.6538887,52.1293746],[-106.6537132,52.1294704],[-106.653457,52.1295421],[-106.6530986,52.1297425],[-106.6530654,52.1297768],[-106.6530603,52.1298135],[-106.6530039,52.1298259],[-106.6529273,52.1298255],[-106.6527741,52.1299222],[-106.6525205,52.1299976],[-106.6521,52.1300667],[-106.6515265,52.1302771],[-106.6512163,52.1304297],[-106.6510647,52.1305647],[-106.6508007,52.1307411],[-106.6504642,52.1310048],[-106.6504106,52.1310473],[-106.6501751,52.1312127],[-106.6500679,52.1313108],[-106.6499046,52.1314696],[-106.6497652,52.1315655],[-106.6494702,52.1319029],[-106.6491041,52.1324438],[-106.6489438,52.1326099],[-106.6485991,52.1331113],[-106.6484357,52.1334164],[-106.6483991,52.1339935],[-106.6483303,52.1342139],[-106.6481797,52.1344621],[-106.648126,52.1347824],[-106.6480244,52.1350435],[-106.6479571,52.1353192],[-106.6477845,52.1356438],[-106.646575,52.1369645],[-106.6462201,52.1372822],[-106.6453152,52.1381845],[-106.6450788,52.1383956],[-106.6444113,52.1392072],[-106.644329,52.1393829],[-106.6442543,52.1397334],[-106.644159,52.1407147],[-106.6440804,52.1411024],[-106.6440326,52.1412927],[-106.6438411,52.1415548],[-106.6436829,52.1418778],[-106.64362323007607,52.142],[-106.63946541131179,52.142],[-106.6394673,52.1419556],[-106.6394673,52.1418679],[-106.6394822,52.1418011],[-106.6395356,52.1417435],[-106.6396102,52.141695],[-106.6396102,52.1416623],[-106.639559,52.1416544],[-106.6395164,52.1416348],[-106.6394822,52.1416007],[-106.6394587,52.1415588],[-106.6394694,52.1415196],[-106.6394865,52.141475],[-106.6394843,52.1414331],[-106.6394651,52.1413572],[-106.6394673,52.1412904],[-106.6394523,52.1412341],[-106.6395057,52.1412432],[-106.6395484,52.1412157],[-106.6395889,52.1411909],[-106.6396252,52.1411817],[-106.6396209,52.1411385],[-106.6396337,52.1411031],[-106.6396764,52.1410887],[-106.6396679,52.1410401],[-106.6396785,52.1409851],[-106.6397191,52.1409262],[-106.6397639,52.1407638],[-106.6396807,52.1406708],[-106.6397473,52.1405379],[-106.6397409,52.1404999],[-106.6397793,52.1404671],[-106.6397943,52.1404213],[-106.639854,52.1403768],[-106.6398497,52.1403152],[-106.6398625,52.1402458],[-106.6399116,52.1401398],[-106.6399221,52.1401182],[-106.6399906,52.1399774],[-106.6400162,52.1398962],[-106.6400759,52.1397691],[-106.6401527,52.1396277],[-106.6402051,52.1395343],[-106.6402359,52.1394915],[-106.6402909,52.1394487],[-106.6402617,52.139421],[-106.6402219,52.1393641],[-106.6402493,52.1393426],[-106.6402882,52.1393329],[-106.6403147,52.1392515],[-106.6403368,52.1392244],[-106.6403302,52.1391742],[-106.6403589,52.1390943],[-106.6403655,52.1390454],[-106.6403943,52.1390115],[-106.6404274,52.1389899],[-106.6407031,52.138613],[-106.641261,52.1371725],[-106.6414805,52.1369535],[-106.6416026,52.1365607],[-106.6418538,52.1360977],[-106.6420399,52.1358178],[-106.6422922,52.135558],[-106.6426875,52.1351059],[-106.6430898,52.1347997],[-106.6433097,52.1345873],[-106.6437121,52.1342514],[-106.6438408,52.1341115],[-106.6440017,52.1339205],[-106.6440688,52.1338119],[-106.6442405,52.1336505],[-106.6443665,52.1335221],[-106.6444188,52.1333236],[-106.6448747,52.1327428],[-106.6449024,52.1326639],[-106.6449431,52.1325929],[-106.6449985,52.1325319],[-106.6450473,52.1324849],[-106.6450929,52.132462],[-106.6451507,52.1324429],[-106.6451641,52.1323738],[-106.6451909,52.1323096],[-106.6452765,52.1321499],[-106.6454645,52.1318815],[-106.6456567,52.1316168],[-106.6458507,52.1313102],[-106.64606,52.1310385],[-106.6464596,52.1305396],[-106.6467225,52.1302449],[-106.64698,52.1299946],[-106.6472106,52.1297509],[-106.647265,52.1297097],[-106.6474172,52.1295945],[-106.6475152,52.129531],[-106.6476358,52.1294673],[-106.6480502,52.1293349],[-106.6485862,52.1291296],[-106.6490221,52.1289784],[-106.6516056,52.1278337],[-106.65189,52.1276811],[-106.6523066,52.1273194],[-106.6524453,52.1270818],[-106.6528184,52.1267251],[-106.6529593,52.1266443],[-106.6537471,52.1257507],[-106.6542583,52.1249942],[-106.6559089,52.1229047],[-106.6577379,52.1218196],[-106.6587456,52.1216257],[-106.6592476,52.1215499],[-106.6603334,52.1211201],[-106.6614921,52.1210905],[-106.6634008,52.1207219],[-106.6685468,52.1208039],[-106.6693269,52.1207743],[-106.6701423,52.1203955],[-106.6715071,52.1201601],[-106.6730659,52.1194864],[-106.6745636,52.1185336],[-106.67611602380703,52.116],[-106.678,52.116],[-106.678,52.11719477779171],[-106.6777674,52.1178059]]]]}}]}
```

</td><td width="50%" valign="top">

The same river in red, with the Downtown roads and the CBD outline:

![South Saskatchewan River in red](Docs/figures/downtown_river_red.png)

</td></tr></table>

<!-- boundary maps: end -->

### Spatial framework

The study correlates three sets of variables: CPTED features of the built environment measured from street photos (X), recorded crime (Y1) and perceived safety on Reddit (Y2). To be correlated, they must share a spatial unit. Following the work plan, this unit is the street segment, a block-length stretch of street between two intersections, and every variable is aggregated to it. The three files in `Data/boundaries/` define the study area and these segments; they hold no photo or crime results.

| File | Role in the framework |
|---|---|
| `central_business_district_osm.geojson` | The study area, Downtown's Central Business District (CBD). Only sample points inside this outline are kept, so it fixes which segments enter the analysis. |
| `osm_roads_downtown_context.geojson` | The street segments. X is measured from photos at points on these roads, and `Scripts/crime_data/hotspots.py` rebuilds the same 218 segments from this file to place each crime record (Y1), so X and Y1 share one unit. |
| `osm_water_downtown_context.geojson` | The river, for the maps only. It plays no part in the analysis. |

Reddit posts rarely name a street, so Y2 is placed by neighbourhood rather than by segment (Decision D2 in `Docs/reddit_pipeline.md`).

### Sampling design

The sample points are where X is observed. They were generated from map data rather than collected in the field. Roads inside the CBD were taken from OpenStreetMap; alleys, driveways and parking aisles were left out for now, although they matter for CPTED and can be added later. Each road was split wherever it met another road to form the segments. Points were spaced about every 50 m along each segment, as the work plan specifies, and placed in the middle of equal-length stretches so that they fall within blocks rather than on intersections. Points outside the CBD were removed, as were points closer than 10 m to one already kept, which would otherwise sample the same spot twice. This produced 423 points on 218 segments. Each point stores the direction of its road, which the image step uses.

### Image collection

The CPTED principles in the work plan (natural surveillance, access control and territoriality, maintenance, activity support and lighting) are judged from the building fronts and the street edge, so each point needs a photo that shows them. No open source has street-level images of Downtown from summer 2026, so each point uses its most recent Mapillary photo from 2020 onward. This keeps the gap to the crime and Reddit data at three to six years, and it means the photos describe the typical built form of each street rather than its exact state in 2026. The photo had to be within 30 m of the point, so that it shows the point's own street, and its camera had to face within 30° of the road's direction, because a pilot found that photos taken from the cross street gave side views looking down the road instead of at the building fronts. The 11 points on bridges and freeways were excluded because they have no building frontage. Photos were found for 246 of the 423 points, on 121 of the 218 segments. Each is a 360° panorama, from which two side views were cut, one facing each side of the street. The image models score each side view, and the scores are averaged per point and then per segment to give the segment's CPTED indicators (X), which are correlated with its crime count (Y1).

## Where it stands

![Workflow status, November 2026](Docs/figures/mid_point_november/fig14_workflow_status.png)

| Step | Status | In numbers |
|---|---|---|
| Crime categories | Done (October) | 5 kinds of crime included, assault conditional, 4 excluded; 9,650 police records for June–August 2026, 2,982 in the study categories |
| Reddit data | Done (October) | 195 posts and 6,452 comments; every table reproduces exactly; 30 automatic checks pass |
| Sample points | Done (October, refined in November) | 423 points on 218 segments; 11 points on bridges or freeways get no photo |
| Street photos | Done (November) | no photos from summer 2026 exist, so each point uses its newest photo from 2020 on that faces along its street: 246 points on 121 of the 218 segments (225 photos from 2020, 21 from 2023) |
| Image models | Done (November) | segmentation, object counts and CLIP scores for all 492 side views (two per point) |
| Accuracy check | Done (November) | 150 side views labelled and scored: street lights (F1 0.92) and seating (0.72) pass, both from the object counts; no CLIP cue passes, and CLIP's land-use label matches 39% of views; the second person's 30 views are next |
| Crime hot spots | Done (November) | 255 of the 257 Downtown study-category records placed on segments; half of them lie on 11 segments |
| Compare streets, crime and Reddit | Next (February–March 2027) | |

Known gaps: the photos are 3–6 years older than the crime and Reddit data, and 97 segments (mostly east–west
streets) have no usable photo, including 5 of the 11 crime hot spots. Details in `Docs/cv_pipeline.md` and
`Docs/crime_data.md`.

| Where crime clusters (heat map; hot-spot streets dashed) | Points with a usable street photo |
|---|---|
| ![Crime hot spots](Docs/figures/mid_point_november/fig09_crime_hotspots.png) | ![Image set](Docs/figures/mid_point_november/fig11_image_set.png) |

All November figures are in `Docs/figures/mid_point_november/`; the October figures, as sent, in
`Docs/figures/mid_point_october/`.

## Words used here

| Word | Meaning |
|---|---|
| Segment | a piece of street between two intersections; the unit the study compares |
| Sample point | a spot on a segment, about every 50 m, where a photo is looked for |
| Side view | a picture cut from a 360° photo that looks at one side of the street (the building fronts) |
| Segmentation | an image model (Mask2Former) that labels every pixel as building, tree, sky, road and so on, giving the share of each |
| CLIP | an image model that scores a photo against a written description, such as "graffiti on a wall" |
| Hot spot | one of the segments that, together, hold half of the recorded crime |
| Flight | the one command (`./flight`) that re-runs the whole project and checks every result against the saved copy |

## Start here

| To find | Open |
|---|---|
| The latest progress update | `Deliverables/2026-10_october_update/` (October). The November midpoint update is kept local until it is sent; `./flight` rebuilds it into `RESULTS_FINAL/EXECUTION-<n>/report/` |
| The literature review (CPTED evidence, crime and perception, pilot sites) | [`Docs/literature review/Master_lit_review.docx`](Docs/literature%20review/Master_lit_review.docx) |
| How the whole study fits together, and how to run it | `Docs/workflow.md` |
| The results, step by step, in notebooks | `Notebooks/` (start with `00_replicate_system.ipynb`) |
| What has been checked, and how | `Docs/verification/october_2026_checks.md`; every number in the updates: `Docs/verification/` |
| Decisions and known problems | image source (Decision D1) in `Docs/cv_pipeline.md`; Reddit's place problem (Decision D2) and limits in `Docs/reddit_pipeline.md`; gaps in the crime data in `Docs/crime_data.md` |
| Any other documentation | `Docs/README.md` |

## Folder map

```
Plan/            governing documents: revised work plan, grant application
Docs/            detailed documentation, verification checks, figures, the literature review
Data/
  reddit_2026-06-01_2026-08-31/   CURRENT  study-period Reddit: raw, cleaned, tables, audits, charts
  reddit_2025-06-11_2026-06-11/   earlier  12-month collection behind the July/August reports (corrected)
  sps_crime_2026-06-01_2026-08-31/ CURRENT  SPS recorded crime (Y1): raw extract, cleaned rows, category counts, per segment
  cv_pilot_2026-10/               CURRENT  CBD sample points, imagery coverage audit, 10-image pilot
  cv_study_2026-11/               CURRENT  study image set (246 points), segmentation/detection/CLIP outputs, labelling sheet
  boundaries/                              CBD polygon (interim, from OSM) and map context
  climate_2010_2025/                       ECCC climate 2010–2025, four prairie cities; kept for possible use
flight           ./flight --execute_flight: the whole pipeline in one command (Scripts/flight/)
Scripts/
  flight/              the flight: execute_flight.py (stages, comparisons, summary), load_models.py, run_notebook.py
  reddit_collection/   Reddit collector (reddit_scraper.py)
  reddit_analysis/     cleaning, tagging, analysis and self-checks (run_all.sh <dataset>)
  crime_data/          cleans the SPS extract into study categories (clean_sps_crime.py); crime per segment (hotspots.py)
  climate_data/        ECCC download scripts behind Data/climate_2010_2025/
  cv_pilot/            sample points, Mapillary imagery, CLIP scoring, Reddit link (pilot.py)
  cv_study/            November: full image set (images.py), segmentation/detection/CLIP (models.py), labelling (validation.py)
  verification/        independent checks of every October claim
  reporting/           figures, report numbers, the October and November .docx builders
  make_handoff.sh      builds a shareable zip without credentials or private text
Notebooks/       notebooks on top of the scripts: replicate the system, Reddit, crime, street images (outputs never committed)
Deliverables/    dated copies of what was sent (2026-08, 2026-10; 2026-11 is kept local until sent); later edits noted in each README
Reference/       literature (incl. computer-vision papers)
Archive/         the August 2026 analysis package (code, data, charts) and surveys dropped in the revised
                 plan (the August CV prototype is in git history)
RESULTS_FINAL/   one EXECUTION-<n>/ folder per flight run, plus executions.csv (git-ignored)
```

## Running

**One command runs the whole pipeline** (repository root):

```bash
./flight --execute_flight             # everything, with fresh Reddit and Mapillary downloads (needs the keys)
./flight --execute_flight --offline   # everything from the saved data, no downloads (about 13 min)
./flight --execute_flight --offline --skip-models   # quick check (about 2–3 min): all but re-running the image models
```

Each run writes everything it produces (results, JSON, status logs, figures, the report, file-by-file comparisons
with the published outputs) into a new `RESULTS_FINAL/EXECUTION-<n>/` and nothing anywhere else. Open its
`FLIGHT_SUMMARY.md` first. Details and options: `Docs/workflow.md` ("One command") and `./flight --help`.

Environment: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` (Python 3.14; the flight does
this itself). Credentials live outside the repository, in `~/.config/computervision_sentinel/secrets.env`
(setup in `Docs/data_ethics.md`): `PRAW_CLIENT_ID`, `PRAW_CLIENT_SECRET`, `PRAW_USER_AGENT`,
`COMPUTERVISION_SENTINEL_HASH_SALT`, `MAPILLARY_TOKEN`. Single steps, to run one on its own, are listed in `Docs/workflow.md`; the most used:

```bash
bash Scripts/reddit_analysis/run_all.sh reddit_2026-06-01_2026-08-31            # Reddit analysis (scratch)
.venv/bin/python Scripts/crime_data/clean_sps_crime.py                            # clean the SPS crime extract
.venv/bin/python Scripts/cv_pilot/pilot.py coverage --out Data/cv_pilot_2026-10/cbd
.venv/bin/python Scripts/verification/verify_october_2026.py                      # re-check October claims
.venv/bin/python Scripts/reporting/make_figures.py                                # rebuild figures
.venv/bin/python Scripts/crime_data/hotspots.py                                   # crime per street segment
.venv/bin/python Scripts/cv_study/models.py                                       # image models (~11 min)
```

**Notebooks** (`Notebooks/`, see its README): open them in VS Code with the `.venv` kernel. They read `Data/` and
never write there, the flight runs 01–03 on every run, and a git filter keeps their outputs out of commits
(after cloning, run `.venv/bin/nbstripout --install` once).

## Ground rules

- Raw data in `Data/*/01_raw_collection/` is never edited; everything else is regenerated by code.
- Numbers in deliverables come from scripts (`Scripts/reporting/report_numbers.py`, `november_numbers.py`).
- Reddit text is not quoted outside the team; images credit Mapillary (CC BY-SA 4.0); maps credit OpenStreetMap.
  See `Docs/data_ethics.md`.

## Team

Co-leads Dr. Varuni Jayasooriya (SENS) and Dr. Timothy Kang (Sociology); collaborators Dr. Khan Wahid (ECE) and
Elisabeth Miller (City of Saskatoon, Neighbourhood Safety and CPTED); research assistant Ryan Ocampo.
