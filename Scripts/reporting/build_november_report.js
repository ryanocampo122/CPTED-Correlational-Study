/*
 * build_november_report.js
 * ========================
 * ComputerVision_Sentinel | November 2026 midpoint progress update, as a Word report and a Markdown page.
 *
 * Inputs : Docs/verification/november_2026_numbers.json   (Scripts/reporting/november_numbers.py)
 *          Docs/figures/mid_point_november/*.png           (Scripts/reporting/make_figures_november.py)
 * Output : Deliverables/2026-11_midpoint/ComputerVision_Sentinel_November2026_Midpoint_Update.docx
 *          Deliverables/2026-11_midpoint/README.md (same text as Markdown)
 *          Both are kept local (git-ignored) until the update is sent; ./flight rebuilds them in RESULTS_FINAL.
 * Each can be redirected (./flight does): --numbers <json> --figures <folder> --out <docx> --md <md>
 *
 * Both files are written from one list of blocks, so the Word report and the Markdown page always say the same.
 * Layout: Times New Roman; title 12 pt bold, headings 11.5 pt, body 11 pt, captions 10 pt, table text 8 pt;
 * black table header rows with white bold text; the same running header on every page; every main section starts
 * on a new page; tables, figures and their captions never break across pages.
 *
 * Usage (repository root):  node Scripts/reporting/build_november_report.js
 */
// File reading and paths
const fs = require("fs");
const path = require("path");
// The Word document parts used here
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, WidthType, AlignmentType,
  HeadingLevel, BorderStyle, ShadingType, LevelFormat, Header, Footer, PageNumber, VerticalAlign,
} = require("docx");

// Input and output locations, each overridable on the command line
const REPO = path.resolve(__dirname, "..", "..");
const arg = (name, dflt) => {
  const i = process.argv.indexOf(name);
  return i > 0 && process.argv[i + 1] ? path.resolve(process.argv[i + 1]) : dflt;
};
const NUMBERS = arg("--numbers", path.join(REPO, "Docs/verification/november_2026_numbers.json"));
const FIG_DIR = arg("--figures", path.join(REPO, "Docs/figures/mid_point_november"));
const OUT = arg("--out", path.join(REPO, "Deliverables/2026-11_midpoint",
  "ComputerVision_Sentinel_November2026_Midpoint_Update.docx"));
const MD = arg("--md", path.join(path.dirname(OUT), "README.md"));
const N = JSON.parse(fs.readFileSync(NUMBERS, "utf8"));
const I = N.images, Y = N.image_years, M = N.models, V = N.validation, C = N.crime, J = N.join;

// Sizes in half-points (Word's unit) for the formatting spec, the text width, and the table look
const SIZE = { title: 24, heading: 23, body: 22, caption: 20, table: 16 };
const FONT = "Times New Roman";
const TEXT_W = 9360;
const HEAD_FILL = "000000";
const BORDER = { style: BorderStyle.SINGLE, size: 4, color: "8C8A84" };
const HEADER_TEXT = "ComputerVision_Sentinel  ·  November 2026 midpoint update";

// Number helpers: thousands separators, percent of a total, one decimal
const fmt = (n) => Number(n).toLocaleString("en-CA");
const pct = (a, b) => Math.round((100 * a) / b);
const one = (n) => Number(n).toFixed(1).replace(/\.0$/, "");

// ----------------------------------------------------------------------------
// Content: one list of blocks, rendered to both Word and Markdown below
// ----------------------------------------------------------------------------
const blocks = [];
let figNo = 0, tableNo = 0;
// Block makers: heading, paragraph, bullet list, numbered list, table with caption, figure with caption
const h1 = (text, newPage = true) => blocks.push({ t: "h1", text, newPage });
const p = (text) => blocks.push({ t: "p", text });
const bullets = (items) => blocks.push({ t: "bullets", items });
const numbered = (items) => blocks.push({ t: "numbered", items });
const refs = (items) => blocks.push({ t: "refs", items });
const table = (caption, headers, rows, widths) => { tableNo += 1; blocks.push({ t: "table", n: tableNo, caption, headers, rows, widths }); };
const figure = (file, widthIn, caption) => { figNo += 1; blocks.push({ t: "figure", n: figNo, file, widthIn, caption }); return figNo; };

const objects = M.objects;
const yrs = I.years;
const g = C.records_by_group;
const cat = C.records_by_category;

// ---- Title and 1. Summary ----
blocks.push({ t: "title", text: "ComputerVision_Sentinel" });
blocks.push({ t: "subtitle", text: "November 2026 midpoint update: street images, image models and crime hot spots" });
blocks.push({ t: "byline", text: "Prepared by Ryan Ocampo" });
blocks.push({ t: "rule", text: "November 2026  ·  revised work plan (October 2026)  ·  study period 1 June – 31 August 2026" });
h1("1. Summary", false);
p(`The November tasks in the revised work plan are to run the segmentation, detection and CLIP steps, to check their ` +
  `accuracy against labelled images, and to map crime hot spots by category. Two are done; for the third, the images ` +
  `are labelled and the scoring is next. The street images follow the image decision taken in November: the newest Mapillary image at ` +
  `each sample point (2020 or 2023), used with the 2026 crime and Reddit data, with the date gap stated as a limitation.`);
bullets([
  `**Street images:** ${I.points_with_image} of the ${I.points} sample points have a usable image, on ` +
  `${I.segments_with_image} of the ${I.segments} street segments (${pct(I.segments_with_image, I.segments)}%). ` +
  `Images now have to face along the point's own street, which fixes the cross-street matches seen in the October pilot.`,
  `**Image models:** one segmentation model measured what share of each of the ${M.views} side views ` +
  `is building, vegetation, sidewalk and so on, and counted street lights, benches and other street furniture; CLIP ` +
  `scored land-use type and nine CPTED cues.`,
  `**Label check:** all ${V.n_labelled} side views drawn blind are labelled and scored. ${V.checks_passing} of the ` +
  `${V.checks.length} checks pass: street lights and seating, both from the object counts. No CLIP cue passes, and ` +
  `CLIP's land-use label matches the labels for ${Math.round(100 * V.typology_accuracy)}% of views.`,
  `**Crime hot spots:** ${C.placed} of the ${C.records} study-category crimes recorded in the CBD were placed on the ` +
  `street segments; half of them lie on just ${C.hotspot_segments.all_study_crime} of the ${C.segments} segments.`,
]);
table("November tasks in the revised work plan (p. 5)", ["November task", "Status", "Evidence"], [
  ["Run segmentation, detection and CLIP", "Done",
    `${M.views} side views from ${M.points} points on ${M.segments} segments (Section 3)`],
  ["Check accuracy against labelled images", "Done",
    `${V.n_labelled} views labelled and scored; ${V.checks_passing} of ${V.checks.length} checks pass (Section 4)`],
  ["Map crime hot spots by category", "Done",
    `${C.placed} of ${C.records} CBD records on segments; maps by group and category (Section 5)`],
], [3000, 1900, 4460]);

// ---- 2. Street images ----
h1("2. The street images");
p(`No open source has street-level images of Downtown from June to August 2026. Following the image decision, each ` +
  `sample point uses its newest Mapillary image captured from 2020 on, within 30 m. The October pilot showed that some ` +
  `images were taken from the cross street, so their side views looked down the wrong road; an image is now used only ` +
  `if the camera faced along the point's own street (within 30°). Points on bridges or the freeway have no building ` +
  `frontage and are left out. Each 360° image is cut into two side views, one facing each side of the street.`);
p(`**Why not only 2023 images:** two ways of using the 2023 images were weighed: with the 2026 crime and Reddit data, ` +
  `or with new 2023 crime and Reddit data so that the dates match. Both depend on 2023 coverage, which is thin. Within ` +
  `30 m, 2023 images exist at ${Y["2023"].points} of the ${I.points} points, on ${Y["2023"].segments} of the ` +
  `${I.segments} segments (${pct(Y["2023"].segments, I.segments)}%), against ${Y["2020"].points} points on ` +
  `${Y["2020"].segments} segments (${pct(Y["2020"].segments, I.segments)}%) for 2020. Matching the dates would also ` +
  `need a new SPS extract, although the SPS crime map warns against comparing its data across years, and a new ` +
  `Reddit collection, which would be smaller: a count-only search with the same terms and settings found ` +
  `${Y.reddit_posts_2023} posts for June–August 2023 against ${Y.reddit_posts_2026} for June–August 2026. The study ` +
  `therefore takes the newest image from 2020 on at each point and keeps the 2026 crime and Reddit data.`);
const fImg = figure("fig11_image_set.png", 3.0, `Which sample points have a usable image. The 2020 survey drove the ` +
  `avenues, so most east–west streets have no image facing along them.`);
table("Image set at the sample points", ["Outcome", "Points"], [
  [`Image from 21 May 2020`, fmt(yrs["2020"])],
  [`Image from 13–14 May 2023`, fmt(yrs["2023"])],
  ["No 2020 or later image within 30 m", fmt(I.no_image_in_search)],
  ["Only images taken from the cross street", fmt(I.lost_to_heading_rule)],
  ["Bridge or freeway (left out)", fmt(I.excluded_bridge + I.excluded_freeway)],
  [`**All points**`, `**${fmt(I.points)}**`],
], [6860, 2500]);
p(`**Assumption:** the street features measured did not change much between the image year and summer 2026, so the ` +
  `images describe the typical built form of each street; this will be tested on the 2014 and 2020 images at the ` +
  `points that have both. **Limitations:**`);
bullets([
  `The images are 3 (2023) or 6 (2020) years older than the crime and Reddit data, and were taken in May, so trees ` +
  `have less foliage than in summer.`,
  `The 2020 images were taken on one day during COVID-19 restrictions, so people and parked cars describe that day; ` +
  `they are flagged and not read as fixed features of the street.`,
  `${I.segments - I.segments_with_image} of the ${I.segments} segments (${pct(I.segments - I.segments_with_image, I.segments)}%) ` +
  `have no usable image, mostly east–west streets (Figure ${fImg}), so the images describe mainly the avenues.`,
]);

// ---- 3. Image models ----
h1("3. What the image models found");
p(`Like Hipp et al. (2022), Zhou et al. (2021), Yue et al. (2022) and Su, Li and Qiu (2023), the study measures each ` +
  `image by the share of the picture taken up by each kind of thing, using a semantic segmentation model. Yue et al. ` +
  `(2022) and Su, Li and Qiu (2023) also counted people and objects with a detection model (Faster R-CNN and Mask ` +
  `R-CNN). Hipp et al. (2022) and Zhou et al. (2021) used DeepLabv3+ and PSPNet trained on the Cityscapes images; none ` +
  `of the four used the model chosen here, Mask2Former trained on Mapillary Vistas. Mapillary Vistas was chosen because ` +
  `its classes include street lights, benches, trash cans and CCTV cameras, which Cityscapes does not have, so one model ` +
  `gives both the segmentation and the street-furniture counts. Su, Li and Qiu (2023) found that benches and street ` +
  `lights near New York subway entrances were associated with lower crime density, which supports counting them here. ` +
  `CLIP, the model validated in October, scores the cues that are hard to segment. Both models are pinned to fixed ` +
  `versions, and a repeat run gives identical results.`);
const s = M.surface_share_pct, ob = (k) => objects[k];
table("What the models found across all side views", ["Measure", "Result"], [
  ["Side views scored", `${fmt(M.views)} (${fmt(M.points)} points, ${fmt(M.segments)} segments)`],
  ["Share of the street scene: building / road / sky", `${one(s.building)}% / ${one(s.road)}% / ${one(s.sky)}%`],
  ["Share of the street scene: vegetation / sidewalk / fence", `${one(s.vegetation)}% / ${one(s.sidewalk)}% / ${one(s.fence)}%`],
  ["Views with a street light (lights found)", `${fmt(ob("street_light").views_with_any)} (${fmt(ob("street_light").total)})`],
  ["Views with a bench / trash can", `${fmt(ob("bench").views_with_any)} / ${fmt(ob("trash_can").views_with_any)}`],
  ["Views with a person / a car (2020: one COVID-19 day)", `${fmt(ob("person").views_with_any)} / ${fmt(ob("car").views_with_any)}`],
  ["Views with a CCTV camera / a bike rack", `${fmt(ob("cctv_camera").views_with_any)} / ${fmt(ob("bike_rack").views_with_any)}`],
], [6060, 3300]);
p(`**Tree crowns:** the segmentation model outlines each tree crown as one solid shape. In May, when most trees are ` +
  `bare, that counted the sky and walls seen between the branches as vegetation. Inside each crown a pixel now stays ` +
  `vegetation only if it looks like part of the tree (a trunk or limb, leaf-green, or dark like a shaded branch); ` +
  `sky-coloured gaps become sky, and the rest take the class beside the tree, usually the building behind it. The ` +
  `colour rules were set by eye on five views, so the vegetation and building shares are still unvalidated.`);
p(`The 2023 images were taken from a car roof, which covers about ${one(M.camera_car_pct_2023_views)}% of each of ` +
  `their side views; the camera car is left out of every share, so those streets are not made to look emptier. ` +
  `The roof's mirror-like paint reflects the scene above it, and in ${M.camera_roof_filled_in} of the ` +
  `${M.views_2023} views the model labelled those reflections instead of the car. The roof sits in nearly the same ` +
  `place in every view of one side, so its typical outline is used there and nothing found on it is counted.`);
figure("fig12_segmentation_examples.png", 5.0, `Four side views and what the segmentation model labelled in them, ` +
  `with tree crowns re-checked by colour. The legend names each colour.`);
figure("fig13_indicator_maps.png", 6.3, `Three image measures per street segment, by quarter of their values. Street lights pass the label check; the ` +
  `building and vegetation shares are not covered by it.`);
const typ = M.typology_counts;
p(`**A warning from the first results:** CLIP's land-use label looks unreliable. It calls ${fmt(typ.surface_parking)} ` +
  `of the ${fmt(M.views)} views a surface parking lot and only ${fmt(typ.commercial_street || 0)} a commercial ` +
  `street, which does not match Downtown, and ${fmt(M.typology_low_confidence)} labels are low-confidence. The ` +
  `label check in Section 4 confirms it.`);

// ---- 4. Label check ----
h1("4. The label check");
p(`No image measure is used until it agrees with the labels. ${V.n_sample} of the ${V.population_views} ` +
  `side views were drawn for labelling by a rule fixed before anyone labelled: ${V.strata} groups by land-use ` +
  `type and image year, each sampled in proportion to its size, spread across the whole CBD. The labelling sheet shows ` +
  `no model output.`);
bullets([
  `Each view is labelled for land-use type and ten cues (graffiti, litter, boarded windows, vacant lot, active ` +
  `storefront, windows overlooking the street, people, fences, seating, a visible street light).`,
  `${V.n_second_coder} of the views also go to a second coder, who labels them without seeing the first coder's sheet.`,
  `A script reports precision, recall and F1 for each cue and the agreement between the two coders. Proposed ` +
  `targets: F1 of at least 0.7 and kappa of at least 0.6; cues that fail are reported and dropped. The sheet records ` +
  `who labelled each view (column labelled_by).`,
]);
const f2 = (x) => (x === null || x === undefined ? "–" : x.toFixed(2));
table(`Each model check against the ${V.n_labelled} labelled views`, ["Cue", "Model", "In labels", "Precision", "Recall", "F1", "Passes"],
  V.checks.map((c) => [c.cue.replace(/_/g, " "), c.model === "object" ? "object count" : "CLIP", `${c.present}`,
    f2(c.precision), f2(c.recall), f2(c.f1), c.passes ? "Yes" : "No"]), [2000, 1500, 1100, 1100, 1000, 900, 1000]);
p(`**Result:** ${V.checks_passing} of the ${V.checks.length} checks pass, both from the segmentation model's object ` +
  `counts: street lights and seating (benches). No CLIP cue passes, and CLIP's land-use label matches the labels for ` +
  `${Math.round(100 * V.typology_accuracy)}% of views, so CLIP is not used for land use or cues. Graffiti, litter and ` +
  `boarded windows appear in only a few labelled views, so their scores rest on very few cases. The ` +
  `${V.n_second_coder} second-coder views are not labelled yet, so agreement between coders is not yet measured.`);

// ---- 5. Crime ----
h1("5. Recorded crime per street segment");
p(`The Saskatoon Police Service gives each record's location as a hundred-block or an intersection, with a point placed ` +
  `30 to 85 m from the street itself. Records are therefore placed by the street they name: a block record goes to the ` +
  `nearest segment of that street, and an intersection record is shared between the segments of its two streets. ` +
  `${fmt(C.placed)} of the ${fmt(C.records)} study-category records in the CBD were placed; ${fmt(C.unplaced)} are on a ` +
  `stretch of Spadina Crescent East with no sample point. The counts per category are small, so the two groups planned ` +
  `in October (property crime; street-based personal crime) are the unit for analysis.`);
table("Recorded crime on the CBD street segments, June–August 2026", ["Group", "Category", "Records"], [
  ["Property", "Theft from vehicle", one(cat.theft_from_vehicle)],
  ["", "Mischief / vandalism", one(cat.mischief_vandalism)],
  ["", "Break and enter", one(cat.break_and_enter)],
  ["", "Auto theft", one(cat.auto_theft)],
  ["Street-based personal", "Assault (conditional: outdoor incidents cannot be separated)", one(cat.assault)],
  ["", "Robbery", one(cat.street_robbery)],
  ["**All study categories**", "", `**${one(g.property + g.street_personal)}**`],
], [2400, 5460, 1500]);
p(`**Hot spots:** crime is concentrated. Half of all study-category crime lies on ` +
  `${C.hotspot_segments.all_study_crime} of the ${C.segments} segments (${pct(C.hotspot_segments.all_study_crime, C.segments)}%): ` +
  `half of property crime on ${C.hotspot_segments.property} segments and half of street-based personal crime on ` +
  `${C.hotspot_segments.street_personal}.`);
figure("fig09_crime_hotspots.png", 6.3, `Where recorded crime clusters, June–August 2026 (heat map). Each record is spread ` +
  `over about 40 m around the location the police data give (a block or an intersection), so brighter colours mean ` +
  `more crime close together. Dashed segments are the hot spots: together they hold half of each group's records.`);
figure("fig10_crime_by_category.png", 6.3, `Recorded crime per street segment for each study category.`);
const top = C.top_segments;
table("The five street segments with the most recorded crime", ["Street", "Length (m)", "Property", "Street-based personal", "All"],
  top.map((r) => [r.road, fmt(r.length_m), one(r.property), one(r.street_personal), one(r.records)]),
  [3160, 1400, 1500, 1900, 1400]);
p(`**Overlap with the street images:** the ${J.segments_with_image} segments with an image hold ` +
  `${fmt(Math.round(J.records_on_imaged_segments))} of the ${fmt(C.placed)} placed records ` +
  `(${pct(J.records_on_imaged_segments, C.placed)}%) and ${J.hotspots_with_image} of the ` +
  `${C.hotspot_segments.all_study_crime} hot spots. The other hot spots are on east–west streets with no usable image, ` +
  `which limits the comparison of street design with crime.`);

// ---- 6. Next steps ----
h1("6. Next steps");
p(`**November to January:**`);
bullets([
  `Have the second coder label ${V.n_second_coder} of the ${V.n_sample} labelled views and measure their agreement; ` +
  `drop the cues that fail, and find a better measure for the CLIP cues or leave them out.`,
  `Test the image-date assumption on the 2014 and 2020 images at the points that have both.`,
  `Combine the validated measures into CPTED indicators per street segment and join them with the crime counts.`,
  `Code the Reddit posts by location, crime type and environmental cue (work plan, December to January).`,
]);

// ---- References (the papers cited in Section 3; APA 7) ----
h1("References", false);
refs([
  `Hipp, J. R., Lee, S., Ki, D., & Kim, J. H. (2022). Measuring the built environment with Google Street View and ` +
  `machine learning: Consequences for crime on street segments. *Journal of Quantitative Criminology*, *38*, 537–565. ` +
  `https://doi.org/10.1007/s10940-021-09506-9`,
  `Su, N., Li, W., & Qiu, W. (2023). Measuring the associations between eye-level urban design quality and on-street ` +
  `crime density around New York subway entrances. *Habitat International*, *131*, Article 102728. ` +
  `https://doi.org/10.1016/j.habitatint.2022.102728`,
  `Yue, H., Xie, H., Liu, L., & Chen, J. (2022). Detecting people on the street and the streetscape physical ` +
  `environment from Baidu Street View images and their effects on community-level street crime in a Chinese city. ` +
  `*ISPRS International Journal of Geo-Information*, *11*(3), Article 151. https://doi.org/10.3390/ijgi11030151`,
  `Zhou, H., Liu, L., Lan, M., Zhu, W., Song, G., Jing, F., Zhong, Y., Su, Z., & Gu, X. (2021). Using Google Street ` +
  `View imagery to capture micro built environment characteristics in drug places, compared with street robbery. ` +
  `*Computers, Environment and Urban Systems*, *88*, Article 101631. https://doi.org/10.1016/j.compenvurbsys.2021.101631`,
]);
blocks.push({ t: "credits", text: `Images: Mapillary and contributors, CC BY-SA 4.0. Map data: © OpenStreetMap ` +
  `contributors (ODbL). Crime data: Saskatoon Police Service.` });

// ----------------------------------------------------------------------------
// Word rendering
// ----------------------------------------------------------------------------
// "plain **bold** plain *italic*" -> text runs at a given size
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const bold = m[0].startsWith("**");
    out.push(new TextRun({ text: bold ? m[0].slice(2, -2) : m[0].slice(1, -1), ...(bold ? { bold: true } : { italics: true }), ...base }));
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...base }));
  return out;
}

// PNG width and height from the file header
function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}

// A table that never breaks: rows cannot split, and every row but the last keeps with the next
function wordTable(b) {
  const cell = (text, w, header, keep) => new TableCell({
    width: { size: w, type: WidthType.DXA },
    borders: { top: BORDER, bottom: BORDER, left: BORDER, right: BORDER },
    shading: header ? { fill: HEAD_FILL, type: ShadingType.CLEAR, color: "auto" } : undefined,
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
    verticalAlign: header ? VerticalAlign.CENTER : VerticalAlign.TOP,
    children: [new Paragraph({ children: runs(String(text), header ? { size: SIZE.table, bold: true, color: "FFFFFF" }
      : { size: SIZE.table }), spacing: { after: 0, line: 240 }, keepNext: keep, keepLines: true })],
  });
  const last = b.rows.length - 1;
  return [
    new Paragraph({ keepNext: true, keepLines: true, spacing: { before: 160, after: 80 },
      children: [new TextRun({ text: `Table ${b.n}. `, bold: true, size: SIZE.caption }), ...runs(b.caption, { size: SIZE.caption })] }),
    new Table({
      width: { size: b.widths.reduce((a, c) => a + c, 0), type: WidthType.DXA }, columnWidths: b.widths,
      rows: [
        new TableRow({ tableHeader: true, cantSplit: true, children: b.headers.map((h, i) => cell(h, b.widths[i], true, true)) }),
        ...b.rows.map((r, j) => new TableRow({ cantSplit: true,
          children: r.map((c, i) => cell(c, b.widths[i], false, j < last)) })),
      ],
    }),
    new Paragraph({ spacing: { after: 120 }, children: [] }),
  ];
}

// A figure kept on the same page as its caption
function wordFigure(b) {
  const full = path.join(FIG_DIR, b.file);
  const { w, h } = pngSize(full);
  const wpx = Math.round(b.widthIn * 96);
  return [
    new Paragraph({ keepNext: true, alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 },
      children: [new ImageRun({ type: "png", data: fs.readFileSync(full),
        transformation: { width: wpx, height: Math.round((wpx * h) / w) },
        altText: { title: `Figure ${b.n}`, description: b.caption, name: b.file } })] }),
    new Paragraph({ keepLines: true, spacing: { after: 200 },
      children: [new TextRun({ text: `Figure ${b.n}. `, bold: true, size: SIZE.caption }), ...runs(b.caption, { size: SIZE.caption })] }),
  ];
}

// Each block as Word paragraphs and tables
const body = [];
// Go through the blocks in order
for (const b of blocks) {
  if (b.t === "title") body.push(new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: b.text, bold: true, size: SIZE.title })] }));
  else if (b.t === "subtitle") body.push(new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: b.text, size: SIZE.heading })] }));
  else if (b.t === "byline") body.push(new Paragraph({ spacing: { after: 40 }, children: runs(b.text, { size: SIZE.body }) }));
  else if (b.t === "rule") body.push(new Paragraph({ spacing: { after: 240 }, border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "000000", space: 6 } }, children: runs(b.text, { size: SIZE.body }) }));
  else if (b.t === "h1") body.push(new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: b.newPage, keepNext: true, keepLines: true, children: [new TextRun(b.text)] }));
  // A paragraph ending in a colon introduces a list, so it stays whole and on the same page as the list's first item
  else if (b.t === "p") {
    const intro = /:(\*\*)?$/.test(b.text.trim());
    body.push(new Paragraph({ children: runs(b.text, { size: SIZE.body }), spacing: { after: 120 }, widowControl: true, keepNext: intro, keepLines: intro }));
  }
  else if (b.t === "bullets") b.items.forEach((x) => body.push(new Paragraph({ numbering: { reference: "bullets", level: 0 }, children: runs(x, { size: SIZE.body }), spacing: { after: 60 }, widowControl: true })));
  else if (b.t === "numbered") b.items.forEach((x) => body.push(new Paragraph({ numbering: { reference: "decisions", level: 0 }, children: runs(x, { size: SIZE.body }), spacing: { after: 80 }, widowControl: true })));
  else if (b.t === "table") body.push(...wordTable(b));
  else if (b.t === "figure") body.push(...wordFigure(b));
  // References: hanging indent, kept together on one page
  else if (b.t === "refs") b.items.forEach((x, i) => body.push(new Paragraph({ children: runs(x, { size: SIZE.body }),
    indent: { left: 360, hanging: 360 }, spacing: { after: 80 }, keepLines: true, keepNext: i < b.items.length - 1 })));
  else if (b.t === "credits") body.push(new Paragraph({ spacing: { before: 240 }, children: runs(b.text, { size: SIZE.caption, color: "52514E" }) }));
}

// The document: fonts and heading style, list styles, page size and margins, header and footer, file properties
const doc = new Document({
  creator: "Ryan Ocampo", lastModifiedBy: "Ryan Ocampo",
  title: "ComputerVision_Sentinel: November 2026 midpoint update",
  description: "Street images, image models and crime hot spots, November 2026",
  styles: {
    default: { document: { run: { font: FONT, size: SIZE.body } } },
    paragraphStyles: [{ id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
      run: { size: SIZE.heading, bold: true, font: FONT }, paragraph: { spacing: { before: 120, after: 160 }, outlineLevel: 0 } }],
  },
  numbering: { config: [
    { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
    { reference: "decisions", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] },
  ] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
      children: [new TextRun({ text: HEADER_TEXT, size: SIZE.caption, color: "52514E" })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ children: [PageNumber.CURRENT], size: SIZE.caption })] })] }) },
    children: body,
  }],
});

// ----------------------------------------------------------------------------
// Markdown rendering (same blocks), figures linked from Docs/figures/mid_point_november/
// ----------------------------------------------------------------------------
const figRel = path.relative(path.dirname(MD), FIG_DIR).split(path.sep).join("/");
const md = [];
// Go through the blocks in order
for (const b of blocks) {
  if (b.t === "title") md.push(`# ${b.text}`, "");
  else if (b.t === "subtitle") md.push(`**${b.text}**`, "");
  else if (b.t === "byline" || b.t === "rule") md.push(b.text, "");
  else if (b.t === "h1") md.push(`## ${b.text}`, "");
  else if (b.t === "p") md.push(b.text, "");
  else if (b.t === "bullets") md.push(...b.items.map((x) => `- ${x}`), "");
  else if (b.t === "numbered") md.push(...b.items.map((x, i) => `${i + 1}. ${x}`), "");
  else if (b.t === "refs") b.items.forEach((x) => md.push(x, ""));
  else if (b.t === "table") md.push(`**Table ${b.n}.** ${b.caption}`, "", `| ${b.headers.join(" | ")} |`,
    `|${b.headers.map(() => "---").join("|")}|`, ...b.rows.map((r) => `| ${r.join(" | ")} |`), "");
  else if (b.t === "figure") md.push(`![Figure ${b.n}](${figRel}/${b.file})`, "", `**Figure ${b.n}.** ${b.caption}`, "");
  else if (b.t === "credits") md.push(`*${b.text}*`, "");
}

// Write both files
fs.mkdirSync(path.dirname(OUT), { recursive: true });
Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT, buf);
  fs.writeFileSync(MD, md.join("\n"));
  console.log(`wrote ${OUT}\nwrote ${MD}`);
});
