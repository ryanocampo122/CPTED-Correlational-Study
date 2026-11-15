/*
 * build_october_report.js
 * =======================
 * CPTED Vision | October 2026 progress report (.docx); its text is kept exactly as the report was sent.
 *
 * Inputs : Docs/verification/october_2026_numbers.json  (Scripts/reporting/report_numbers.py)
 *          Docs/figures/mid_point_october/*.png          (Scripts/reporting/make_figures.py)
 * Output : Deliverables/2026-10_october_update/CPTED_Vision_October2026_Progress_Report.docx
 * Each can be redirected (./flight does): --numbers <json> --figures <folder> --out <docx>
 *
 * Layout: Times New Roman 11 pt, US Letter, 1-inch margins, running header from page 2.
 * Every main section (and every 3.x subsection) starts at the top of a new page, and each
 * page is filled with whole blocks: paragraphs never break across pages (keepLines),
 * headings, captions and figures keep with what follows (keepNext), and table rows
 * never split. Check the layout after any content change (README in this folder).
 *
 * Usage (repository root):  node Scripts/reporting/build_october_report.js
 */
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, WidthType,
  AlignmentType, HeadingLevel, BorderStyle, ShadingType, LevelFormat, Header, Footer, PageNumber,
  TabStopType, VerticalAlign,
} = require("docx");

const REPO = path.resolve(__dirname, "..", "..");
// --numbers / --figures / --out override the published locations below.
const arg = (name, dflt) => {
  const i = process.argv.indexOf(name);
  return i > 0 && process.argv[i + 1] ? path.resolve(process.argv[i + 1]) : dflt;
};
const NUMBERS = arg("--numbers", path.join(REPO, "Docs/verification/october_2026_numbers.json"));
const FIG_DIR = arg("--figures", path.join(REPO, "Docs/figures/mid_point_october"));
const OUT = arg("--out", path.join(REPO, "Deliverables/2026-10_october_update",
  "CPTED_Vision_October2026_Progress_Report.docx"));
const OUT_DIR = path.dirname(OUT);
const N = JSON.parse(fs.readFileSync(NUMBERS, "utf8"));
const R = N.reddit, P = N.points, I = N.imagery;

const FONT = "Times New Roman";
const TEXT_W = 9360;                 // 6.5 in in DXA
const HEAD_FILL = "000000";          // table header bar: black, white bold text
const BORDER = { style: BorderStyle.SINGLE, size: 4, color: "8C8A84" };
const fmt = (n) => n.toLocaleString("en-CA");

// Figures in the order they appear; text refers to them by key so numbers stay right.
const FIGS = ["workflow", "timeline", "area", "weekly", "anchors", "years", "pilot"];
const F = Object.fromEntries(FIGS.map((k, i) => [k, i + 1]));

// "plain **bold** plain *italic*" -> runs
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const s = m[0];
    if (s.startsWith("**")) out.push(new TextRun({ text: s.slice(2, -2), bold: true, ...base }));
    else out.push(new TextRun({ text: s.slice(1, -1), italics: true, ...base }));
    last = m.index + s.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...base }));
  return out;
}

const para = (text, opts = {}) => new Paragraph({ children: runs(text), spacing: { after: 120 }, keepLines: true, ...opts });
const h1 = (text, newPage = true) => new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: newPage,
  children: [new TextRun(text)] });
const h2 = (text, newPage = false) => new Paragraph({ heading: HeadingLevel.HEADING_2, pageBreakBefore: newPage,
  children: [new TextRun(text)] });
const bullet = (text, opts = {}) => new Paragraph({ numbering: { reference: "bullets", level: 0 }, children: runs(text),
  spacing: { after: 60 }, keepLines: true, ...opts });
const numbered = (text) => new Paragraph({ numbering: { reference: "decisions", level: 0 },
  children: runs(text), spacing: { after: 100 }, keepLines: true });

// Numbered table caption, kept on the same page as its table.
let tableNo = 0;
function tableCaption(text) {
  tableNo += 1;
  return new Paragraph({ keepNext: true, keepLines: true, spacing: { before: 160, after: 80 },
    children: [new TextRun({ text: `Table ${tableNo}. `, bold: true, size: 20 }), ...runs(text, { size: 20 })] });
}

// widths in DXA (1/1440 inch). Header row repeats on each page; rows never split.
function table(headers, rows, widths, opts = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  const cell = (text, w, header, shade) => new TableCell({
    width: { size: w, type: WidthType.DXA },
    borders: { top: BORDER, bottom: BORDER, left: BORDER, right: BORDER },
    shading: header ? { fill: HEAD_FILL, type: ShadingType.CLEAR, color: "auto" }
      : shade ? { fill: shade, type: ShadingType.CLEAR, color: "auto" } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    verticalAlign: header ? VerticalAlign.CENTER : VerticalAlign.TOP,
    children: String(text).split("\n").map((line) => new Paragraph({
      children: runs(line, header ? { size: 22, bold: true, color: "FFFFFF" } : { size: 22 }),
      spacing: { after: 0, line: 240 }, keepNext: header || undefined, keepLines: true,
    })),
  });
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      new TableRow({ tableHeader: true, cantSplit: true,
        children: headers.map((h, i) => cell(h, widths[i], true)) }),
      ...rows.map((r) => new TableRow({ cantSplit: true,
        children: r.map((c, i) => cell(c, widths[i], false, opts.shadeFirst && i === 0 ? "F2F2F2" : undefined)) })),
    ],
  });
}

// PNG width/height from the IHDR chunk (bytes 16-23).
function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}

// Centred image scaled to widthIn inches, followed by its numbered caption.
function figure(key, file, widthIn, caption, opts = {}) {
  const n = F[key];
  const full = path.join(FIG_DIR, file);
  const { w, h } = pngSize(full);
  const wpx = Math.round(widthIn * 96);
  return [
    new Paragraph({ keepNext: true, alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 },
      pageBreakBefore: opts.newPage || undefined,
      children: [new ImageRun({ type: "png", data: fs.readFileSync(full),
        transformation: { width: wpx, height: Math.round(wpx * h / w) },
        altText: { title: `Figure ${n}`, description: caption.replace(/\*/g, ""), name: file } })] }),
    new Paragraph({ keepLines: true, keepNext: opts.keepNext || undefined, spacing: { after: 200 },
      children: [new TextRun({ text: `Figure ${n}. `, bold: true, size: 20 }), ...runs(caption, { size: 20 })] }),
  ];
}

// ----------------------------------------------------------------------------
// Content
// ----------------------------------------------------------------------------
const dt = R.downtown, rb = R.riverbank, dtj = R.downtown_june_collection, rbj = R.riverbank_june_collection;
const newest = I.newest;
const pct = (a, b) => Math.round((100 * a) / b);
const children = [];
const add = (...xs) => xs.flat().forEach((x) => children.push(x));

// ---------------- Page 1: title and summary ----------------
add(
  new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: "CPTED Vision", bold: true, size: 32 })] }),
  new Paragraph({ spacing: { after: 60 },
    children: [new TextRun({ text: "October 2026 progress report: work-plan tasks and verification", size: 26 })] }),
  new Paragraph({ spacing: { after: 40 }, children: runs(
    "Prepared by Ryan Ocampo for Dr. Varuni Jayasooriya and Dr. Timothy Kang") }),
  new Paragraph({ spacing: { after: 240 }, border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "000000", space: 6 } },
    children: runs("17 October 2026  ·  revised work plan (October 2026)  ·  study period 1 June – 31 August 2026") }),
  h1("1. Summary", false),
  para(`Three of the four October tasks in the revised work plan are reported here, and all three are done; the fourth, ` +
    `generating sample points, is still being refined and will be reported separately. For street-level images, the ` +
    `October goal was to ` +
    `validate the method rather than to deliver the full image set: the project can source street images as secondary ` +
    `data at its sample points, and the downloaded CLIP ViT-B/32 model can read them in a pipeline built for a small ` +
    `sample. No imagery from June to August 2026 exists yet for Downtown, so sourcing the full set is the next step.`),
  bullet(`**Crime categories are final and the crime data have been obtained:** five categories included, assault ` +
    `conditional on separating outdoor incidents, four excluded (Table 2). The data will be added to the project folder.`),
  bullet(`**Reddit now covers the study period:** ${R.posts} posts and ${fmt(R.comments)} comments from 1 June to 31 August 2026. ` +
    `Every published table reproduces exactly from the raw data and ${R.selfchecks_pass} automated checks pass.`),
  bullet(`**Street images (method validated):** ${I.pilot_n} Mapillary images were sourced at spread sample points, cut into ` +
    `street-facing views, scored by the CLIP ViT-B/32 model and joined to the Reddit data (Section 3.3). Section 4 ` +
    `explains the model and why it was chosen.`),
  tableCaption("October tasks in the revised work plan (p. 5)"),
  table(["October task", "Status", "Evidence"], [
    ["Finalize crime categories", "Done", "Work plan p. 4 (Table 2); SPS crime data obtained"],
    ["Extend Reddit collection to June–August 2026", "Done, verified",
      `${R.posts} posts, ${fmt(R.comments)} comments; ${R.reproduce_junaug[0]} of ${R.reproduce_junaug[1]} tables reproduce exactly`],
    ["Generate sample points", "In progress", "Being refined; to be reported separately"],
    ["Collect street-level images", "Done: method validated",
      `${I.pilot_n} Mapillary images sourced and read by CLIP ViT-B/32; full set to be sourced (Section 3.3)`],
  ], [3000, 2100, 4260]),
);

// ---------------- Page 2: where the project stands ----------------
add(
  h1("2. Where the project stands"),
  para(`The study keeps the framework proposed in the AIRI grant but uses data that are already public: street images ` +
    `show what streets look like, police records show where crime is recorded, and Reddit shows how safe people feel. ` +
    `Figure ${F.workflow} follows each kind of data through the steps of the study, and Figure ${F.timeline} places the ` +
    `work on the timeline. Checking accuracy is a step of its own: for the larger grant, the framework is only as ` +
    `credible as the evidence that each automated measure agrees with human judgement.`),
  figure("workflow", "fig01_workflow_status.png", 5.6, `How the study works, step by step, and where each step stands ` +
    `on 17 October 2026.`),
  figure("timeline", "fig02_timeline.png", 5.0, `Timeline from the work plan. In October the image collection method and ` +
    `the CLIP ViT-B/32 model were validated on ${I.pilot_n} sourced images.`),
);

// ---------------- Page 3: 3.1 crime categories ----------------
add(
  h1("3. The October tasks"),
  h2("3.1 Crime categories (final)"),
  para(`The categories are those in the work plan (p. 4), and the SPS crime data for them have been obtained. Table 2 ` +
    `adds the matching SPS category for each. If counts are low, categories will be grouped into property crime ` +
    `(break and enter, theft from vehicle, auto theft, mischief) and street-based personal crime (robbery, outdoor assault).`),
  tableCaption("Final crime categories and the SPS categories they map to"),
  table(["Category", "Decision", "SPS category", "Note"], [
    ["Break and enter", "Included", "Break & enter", "—"],
    ["Theft from vehicle", "Included", "Theft from vehicle", "—"],
    ["Auto theft", "Included", "Auto theft", "—"],
    ["Mischief / vandalism", "Included", "Mischief", "—"],
    ["Street robbery", "Included", "Robbery", "SPS category includes commercial robbery; premise type needed to keep street robbery only"],
    ["Assault", "Conditional", "Assault", "Include only if outdoor incidents can be separated; the public map shows no premise type"],
    ["Fraud, homicide, sexual assault, drug offences", "Excluded", "—", "Reasons as in the work plan"],
  ], [2050, 1250, 2000, 4060]),
  para(`SPS category names follow the SPS public crime map and will be confirmed against the data obtained. The public ` +
    `map states that its points show "the general area in which the incident occurred and are not intended to identify ` +
    `the exact incident location", so the precision of the locations will be checked before they are matched to 50 m ` +
    `street segments.`,
    { spacing: { before: 160, after: 120 } }),
  para(`The categories line up with the hypotheses: opportunistic crime for H1, mischief and property crime for H2, ` +
    `vehicle-related crime and street robbery for H3. The Reddit crime search terms (Section 3.2) were aligned with ` +
    `the same categories.`),
);

// ---------------- Pages 4-5: 3.2 Reddit ----------------
add(
  h2("3.2 Reddit collection for June to August 2026", true),
  para(`**What was adjusted.** The collector now takes the study window in Saskatoon time (1 June to 31 August 2026). It searches ` +
    `the ${R.seeds_safety} original safety terms plus ${R.seeds_crime} crime terms aligned with the categories above ` +
    `(e.g. "broken into", "catalytic converter", "robbed"), under ${R.sorts} search orders each. Locations and environmental ` +
    `cues are tagged on whole words, with references to other cities' downtowns removed after a first-pass review (to be confirmed by hand). Sentiment uses ` +
    `VADER adjusted so the search words themselves ("safe", "safety") do not bias it. Comments written after 31 August are ` +
    `flagged and left out of the analysis (${R.comments_late} of ${fmt(R.comments)}).`),
  para(`**What was collected.** ${R.posts} posts (June ${R.posts_by_month.Jun}, July ${R.posts_by_month.Jul}, August ` +
    `${R.posts_by_month.Aug}) with ${fmt(R.comments)} comments, ${fmt(R.comments_in_window)} of them written inside the ` +
    `window. Downtown/CBD has ${dt.n} records (${dt.posts} posts and ${dt.comments} comments from ${dt.threads} threads). ` +
    `Every published table reproduces exactly from the raw files, and ${R.selfchecks_pass} automated checks pass.`),
  para(`**What it shows (descriptive only).** In summer 2026, Downtown/CBD is discussed with the same share of negative ` +
    `mentions as the corpus as a whole: ${dt.pct_neg}% (95% CI ${dt.pct_lo}–${dt.pct_hi}) against ${R.all_comments_pct_neg}% for all ` +
    `comments (Figure ${F.area}). Riverbank/Meewasin has the highest share, ${rb.pct_neg}% (${rb.pct_lo}–${rb.pct_hi}; ${rb.n} records). ` +
    `The earlier 12-month collection had Downtown at ${dtj.pct_neg}% and Riverbank at ${rbj.pct_neg}%, but the windows and ` +
    `search terms differ, so this is not a trend.`, { keepNext: true }),
  figure("area", "fig03_reddit_by_area.png", 5.8, `Share of negative mentions by area, June to August 2026, for the ${R.areas_15} areas ` +
    `with at least 15 mentions. Lines are 95% confidence intervals from resampling whole threads; the dashed line is all comments.`),
  para(`**Coverage over the summer.** Posts fall on ${R.days_with_posts} of the 92 days and in every week of the window ` +
    `(Figure ${F.weekly}). Some threads are off-topic because Reddit's search also matches fields other than the post ` +
    `text; dropping them barely changes Downtown (${R.dt_on_topic_pct_neg}% negative across ${R.dt_on_topic_n} records).`,
    { pageBreakBefore: true, keepNext: true }),
  figure("weekly", "fig04_reddit_weekly.png", 5.4, `Posts collected per week, 1 June to 31 August 2026. Darker bars: posts whose own ` +
    `title or body contains a search term.`),
  para(`**How finely Reddit can be located.** Reddit places a record in a neighbourhood, not on a street segment. Of ` +
    `${dt.n} Downtown records, the most-named street, ${R.anchor_top}, appears in ${R.anchor_top_n}, and ${R.anchors_under5} of ` +
    `${R.anchors_n} streets and landmarks appear fewer than 5 times (Figure ${F.anchors}), so Reddit can be compared with ` +
    `the other data by neighbourhood but not street by street.`,
    { keepNext: true }),
  figure("anchors", "fig08_reddit_place_anchors.png", 4.8, `Downtown Reddit records that name each street or landmark, ` +
    `June to August 2026.`),
);

// ---------------- Pages 6-7: 3.3 images ----------------
add(
  h2("3.3 Street-level images", true),
  para(`**What October set out to show.** The October image task was a method check at the halfway point, not the delivery ` +
    `of the full image set for the study period. Its aim was to validate that CPTED Vision has a working way to source ` +
    `street-level images as secondary data at its sample points, and that the downloaded image model can read those images ` +
    `and return CPTED measures. Both were shown. ${I.pilot_n} spatially spread points were taken in an order fixed before any ` +
    `image was seen; the newest Mapillary image at each was downloaded (2014: ${I.pilot_years["2014"] || 0}, 2019: ` +
    `${I.pilot_years["2019"] || 0}, 2020: ${I.pilot_years["2020"] || 0}, 2023: ${I.pilot_years["2023"] || 0}); 360° images ` +
    `were cut into street-facing views; the CLIP ViT-B/32 model scored every image (Section 4); and the results were ` +
    `joined to the Downtown Reddit data.`),
  para(`**Why this is a sound way to work.** The steps follow published street-view crime studies. He, Páez and Liu (2017) ` +
    `show that audits of street imagery give reliable measures of physical disorder such as graffiti, broken windows and ` +
    `vacant buildings, and advise checking image availability in the study area before collecting. Hipp et al. (2022) ` +
    `sampled images every 20 m along every street segment and measured the built environment with a pretrained ` +
    `deep-learning model; Yue et al. (2022), Zhou et al. (2021) and Su, Li and Qiu (2023) also applied pretrained models to ` +
    `street images to measure features linked to crime. CPTED Vision's points about 50 m apart on street segments, its ` +
    `availability check and its pretrained model follow the same pattern.`),
  para(`**Study-period imagery.** The availability check found images within 30 m of ${I.any} of ${I.points} points, but none ` +
    `captured from June to August 2026; the newest are from 2023 (${newest["2023"]} points) and 2020 (${newest["2020"]}) ` +
    `(Figure ${F.years}). Sourcing the full set is therefore the next step. Published studies either keep imagery within ` +
    `one to three years of the crime data or justify a longer gap by showing the built environment was stable (He, Páez ` +
    `and Liu 2017). Google Street View is not an option: its terms (Maps Platform Terms of Service 3.2.3) prohibit bulk ` +
    `download of Street View images and their use to train, test or validate models.`, { keepNext: true }),
  figure("years", "fig06_imagery_by_year.png", 5.2, `CBD sample points by the year of their newest Mapillary image within 30 m.`),
  para(`**What the ten images show.** Figure ${F.pilot} shows four of the ten images with what the pipeline got right and wrong.`,
    { pageBreakBefore: true, keepNext: true }),
  figure("pilot", "fig07_pilot_images.png", 6.5, `Four of the ten validation images. Imagery © Mapillary contributors, CC BY-SA 4.0.`,
    { keepNext: true }),
  bullet(`Side views cut from 360° images show building frontages well (a), which is what natural-surveillance cues need.`),
  bullet(`${I.pilot_cross_street} of ${I.pilot_n} images were taken on the cross street at an intersection (c). The matching rule ` +
    `will require the camera to point within 30° of the street's direction.`),
  bullet(`Some CLIP land-use labels are plainly wrong (a), which is why every CLIP measure will be checked against about ` +
    `150 hand-labelled images before it is used.`),
);

// ---------------- Page 9: 4. the image model ----------------
add(
  h1("4. The image model: CLIP ViT-B/32"),
  para(`**What it is.** CLIP (Contrastive Language–Image Pre-training; Radford et al. 2021) is an open model from OpenAI, ` +
    `trained on about 400 million images paired with their captions. It places an image and a written description in ` +
    `the same numerical space, so it can score an image against any description, such as "graffiti on a wall", without ` +
    `being trained on labelled examples (zero-shot use). ViT-B/32 is one of its smaller versions: a base-size Vision ` +
    `Transformer that reads an image in 32 × 32-pixel patches.`),
  para(`**How the pipeline uses it.** Each street-facing view is cut into three square crops and compared with plain-text ` +
    `prompts for ${I.typology_labels} land-use types and ${I.cues} CPTED cues, such as graffiti, litter, boarded windows and ` +
    `active storefronts, each scored against a contrasting prompt. Streetlights are left to object detection, because thin ` +
    `objects are a known weakness of CLIP.`),
  para(`**Why it was chosen.**`, { keepNext: true, spacing: { after: 60 } }),
  bullet(`**It needs no training labels.** No hand-labelled Saskatoon images exist yet, so a zero-shot model can run now; ` +
    `the ~150 hand labels will test it rather than train it.`),
  bullet(`**It reaches cues that other models miss.** The studies in Table 3 used semantic segmentation (DeepLabv3+, PSPNet) ` +
    `for scene composition and object detection (Faster R-CNN, Mask R-CNN) to count people and cars. Disorder cues such as ` +
    `graffiti, boarded windows and vacancy, which He, Páez and Liu (2017) recorded by hand, have no segmentation class; ` +
    `CLIP can score them from a description.`),
  bullet(`**It is small, open and transparent.** It ran on a laptop, its weights are public so results can be reproduced, ` +
    `and its prompts are plain sentences that criminologists and City staff can check.`),
  tableCaption("Street-image methods in the computer-vision studies that support this work"),
  table(["Study", "Images", "Models", "What it supports here"], [
    ["He, Páez and Liu (2017)", "Google Street View audit", "Human auditors",
      "Reliable disorder measures; check availability first"],
    ["Hipp et al. (2022)", "Google Street View every 20 m (Santa Ana)", "DeepLabv3+",
      "Sampling on street segments; pretrained model"],
    ["Zhou et al. (2021)", "Google Street View at incident sites", "PSPNet; Streetscore",
      "Pretrained models link built form to street robbery"],
    ["Yue et al. (2022)", "Baidu Street View, a large Chinese city", "Faster R-CNN; PSPNet",
      "Combined models give complementary measures"],
    ["Su, Li and Qiu (2023)", "Street view at New York subway entrances", "PSPNet; Mask R-CNN",
      "Design quality measured from images relates to crime"],
  ], [1850, 2700, 1900, 2910]),
  para(`**Subject to change.** CLIP is the starting model, not a fixed choice. It is strong at matching whole scenes to a ` +
    `description but weaker at fine distinctions and at counting objects (Radford et al. 2021), and street imagery shows ` +
    `small items less well (He, Páez and Liu 2017). Each CLIP measure will be checked against about 150 hand-labelled ` +
    `images; a cue that falls short will move to a model built for it, such as segmentation (DeepLabv3+, chosen by Hipp ` +
    `et al. 2022 for its accuracy on street scenes) or object detection (Yue et al. 2022; Su, Li and Qiu 2023), or be ` +
    `dropped. Changing a model changes one step of the pipeline, not the study design.`,
    { spacing: { before: 140, after: 0 } }),
);

// ---------------- Last page: appendix ----------------
add(
  h1("Appendix: where things are"),
  para(`Everything is in the research folder, which is under version control. The detailed documentation lives there; ` +
    `this report summarizes it.`),
  tableCaption("Repository map"),
  table(["Folder", "Contents"], [
    ["Plan/", "Revised work plan; AIRI grant application"],
    ["Docs/", "Workflow, methods, decision and issue log, validation plan, verification checks, figures"],
    ["Data/reddit_2026-06-01_2026-08-31/", "Study-period Reddit data: raw, cleaned, tables, audits, charts"],
    ["Data/cv_pilot_2026-10/", "Sample points, imagery coverage audit, 10-image validation run"],
    ["Scripts/", "Reddit collection and analysis, image pipeline, verification, figures and this report"],
    ["Deliverables/", "Dated copies of what was sent: July, August, October 2026"],
    ["Reference/, Archive/", "Literature (incl. the computer-vision papers) and presentations; dropped surveys"],
  ], [3600, 5760], { shadeFirst: true }),
  new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 320, after: 100 }, children: [new TextRun("References")] }),
  para(`He, L., Páez, A., & Liu, D. (2017). Built environment and violent crime: An environmental audit approach using ` +
    `Google Street View. *Computers, Environment and Urban Systems*, 66, 83–95.`, { spacing: { after: 80 } }),
  para(`Hipp, J. R., Lee, S., Ki, D., & Kim, J. H. (2022). Measuring the built environment with Google Street View and ` +
    `machine learning: Consequences for crime on street segments. *Journal of Quantitative Criminology*, 38, 537–565.`,
    { spacing: { after: 80 } }),
  para(`Radford, A., Kim, J. W., Hallacy, C., Ramesh, A., Goh, G., Agarwal, S., Sastry, G., Askell, A., Mishkin, P., ` +
    `Clark, J., Krueger, G., & Sutskever, I. (2021). Learning transferable visual models from natural language ` +
    `supervision. *Proceedings of the 38th International Conference on Machine Learning*, PMLR 139, 8748–8763.`,
    { spacing: { after: 80 } }),
  para(`Su, N., Li, W., & Qiu, W. (2023). Measuring the associations between eye-level urban design quality and on-street ` +
    `crime density around New York subway entrances. *Habitat International*, 131, 102728.`, { spacing: { after: 80 } }),
  para(`Yue, H., Xie, H., Liu, L., & Chen, J. (2022). Detecting people on the street and the streetscape physical ` +
    `environment from Baidu Street View images and their effects on community-level street crime in a Chinese city. ` +
    `*ISPRS International Journal of Geo-Information*, 11, 151.`, { spacing: { after: 80 } }),
  para(`Zhou, H., Liu, L., Lan, M., et al. (2021). Using Google Street View imagery to capture micro built environment ` +
    `characteristics in drug places, compared with street robbery. *Computers, Environment and Urban Systems*, 88, 101631.`,
    { spacing: { after: 80 } }),
);

// ----------------------------------------------------------------------------
const small = { size: 18, color: "4D4D4D" };
const runningHeader = new Header({ children: [new Paragraph({
  tabStops: [{ type: TabStopType.RIGHT, position: TEXT_W }],
  border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "000000", space: 4 } },
  children: [new TextRun({ text: "CPTED Vision  ·  October 2026 progress report", ...small }),
    new TextRun({ text: "\t17 October 2026", ...small })] })] });
const pageFooter = new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
  children: [new TextRun({ children: ["Page ", PageNumber.CURRENT, " of ", PageNumber.TOTAL_PAGES], ...small })] })] });

const doc = new Document({
  creator: "Ryan Ocampo",
  title: "CPTED Vision: October 2026 progress report",
  description: "October 2026 work-plan tasks and verification",
  styles: {
    default: { document: { run: { font: FONT, size: 22 }, paragraph: { spacing: { line: 259 } } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 26, bold: true, color: "000000" },
        paragraph: { spacing: { before: 0, after: 140 }, keepNext: true, keepLines: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 23, bold: true, color: "000000" },
        paragraph: { spacing: { before: 200, after: 100 }, keepNext: true, keepLines: true, outlineLevel: 1 } },
    ],
  },
  numbering: {
    config: [
      { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 360, hanging: 260 } } } }] },
      { reference: "decisions", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 360, hanging: 360 } } } }] },
    ],
  },
  sections: [{
    properties: { titlePage: true, page: { size: { width: 12240, height: 15840 },
      margin: { top: 1440, right: 1440, bottom: 1440, left: 1440, header: 708, footer: 708 } } },
    headers: { default: runningHeader, first: new Header({ children: [new Paragraph({ children: [] })] }) },
    footers: { default: pageFooter, first: pageFooter },
    children,
  }],
});

fs.mkdirSync(OUT_DIR, { recursive: true });
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUT, buf); console.log("wrote", OUT); });
