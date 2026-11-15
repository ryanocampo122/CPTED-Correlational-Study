/**
 * 06_build_meewasin_memo_docx.js
 * ================================
 * CPTED Vision | Builds the short-form data quality memo
 *
 * ARCHIVAL (October 2026): rebuilds the memo as sent in July/August, except that the
 * project name now reads CPTED Vision.
 * Its hard-coded numbers predate the October corrections (environmental-cue
 * tagging, other-city exclusions, adjusted sentiment) and are not current.
 * It is not run by run_all.sh. See Scripts/reddit_analysis/README.md.
 *
 * PURPOSE
 * Builds the Meewasin data-quality memo (memo.docx): the earlier,
 * narrower writeup focused specifically on the Riverbank/Meewasin
 * location-matching issue (see 01_audit_location_tagging.py for the
 * underlying analysis). Superseded in scope by the full August report
 * (07_build_august_report_docx.js), kept here for reference since it's
 * still referenced from that report's appendix.
 *
 * INPUT
 * Numbers/quotes in this script are hardcoded from the output of
 * 01_audit_location_tagging.py and 05_extract_example_quotes.py at the
 * time this memo was written. They do not change when the analysis is re-run.
 *
 * OUTPUT
 *   memo.docx
 *
 * USAGE
 *   npm install docx   (if not already installed)
 *   node 06_build_meewasin_memo_docx.js
 */

const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle, AlignmentType
} = require("docx");

const PAGE_W = 12240, PAGE_H = 15840; // US Letter

function h1(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_1, spacing: { before: 280, after: 140 } });
}
function h2(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_2, spacing: { before: 220, after: 100 } });
}
function p(text, opts = {}) {
  return new Paragraph({
    children: [new TextRun({ text, ...opts })],
    spacing: { after: 160 },
  });
}
function bullet(text, opts = {}) {
  return new Paragraph({
    children: [new TextRun({ text, ...opts })],
    bullet: { level: 0 },
    spacing: { after: 80 },
  });
}
function quoteBlock(meta, text) {
  return [
    new Paragraph({
      children: [new TextRun({ text: meta, italics: true, size: 18, color: "666666" })],
      spacing: { before: 120, after: 40 },
    }),
    new Paragraph({
      children: [new TextRun({ text: `"${text}"`, size: 20 })],
      indent: { left: 360 },
      border: { left: { style: BorderStyle.SINGLE, size: 12, color: "999999", space: 8 } },
      spacing: { after: 160 },
    }),
  ];
}

function cell(text, opts = {}) {
  return new TableCell({
    width: { size: opts.width || 2000, type: WidthType.DXA },
    shading: opts.header ? { type: ShadingType.CLEAR, fill: "2F5496" } : undefined,
    margins: { top: 80, bottom: 80, left: 100, right: 100 },
    children: [new Paragraph({
      children: [new TextRun({
        text,
        bold: !!opts.header,
        color: opts.header ? "FFFFFF" : "000000",
        size: 20,
      })],
    })],
  });
}

function compareTable() {
  const colW = [2600, 3200, 3200];
  const header = new TableRow({
    children: [
      cell("", { width: colW[0], header: true }),
      cell("Tagged \u201cRiverbank / Meewasin\u201d (raw)", { width: colW[1], header: true }),
      cell("Genuinely mention river/Meewasin (word-boundary)", { width: colW[2], header: true }),
    ],
  });
  const rows = [
    ["Posts", "46", "8"],
    ["Comments", "679", "114"],
    ["False-positive rate", "\u2014", "83% (driver/drivers = 542 of 565 false hits)"],
  ];
  return new Table({
    width: { size: colW[0] + colW[1] + colW[2], type: WidthType.DXA },
    columnWidths: colW,
    rows: [header, ...rows.map(r => new TableRow({
      children: [cell(r[0], { width: colW[0] }), cell(r[1], { width: colW[1] }), cell(r[2], { width: colW[2] })],
    }))],
  });
}

function findingsTable() {
  const colW = [3400, 2800, 2800];
  const header = new TableRow({
    children: [
      cell("Metric", { width: colW[0], header: true }),
      cell("Raw tag (incl. false positives)", { width: colW[1], header: true }),
      cell("Corrected (genuine mentions)", { width: colW[2], header: true }),
    ],
  });
  const rows = [
    ["Mean sentiment (comments)", "+0.01 (\u2248neutral)", "+0.31 (net positive)"],
    ["Negative share of comments", "47%", "23% (26 of 114)"],
    ["Most negative time-of-day", "Evening", "Evening (but n=29, small)"],
    ["Lighting mentioned in negative comments", "15\u201316%", "Present, but not in top negative comments by score"],
  ];
  return new Table({
    width: { size: colW[0] + colW[1] + colW[2], type: WidthType.DXA },
    columnWidths: colW,
    rows: [header, ...rows.map(r => new TableRow({
      children: [cell(r[0], { width: colW[0] }), cell(r[1], { width: colW[1] }), cell(r[2], { width: colW[2] })],
    }))],
  });
}

const doc = new Document({
  sections: [{
    properties: { page: { size: { width: PAGE_W, height: PAGE_H }, margin: { top: 1080, bottom: 1080, left: 1260, right: 1260 } } },
    children: [
      new Paragraph({
        children: [new TextRun({ text: "CPTED Vision", bold: true, size: 40, color: "2F5496" })],
        spacing: { after: 40 },
      }),
      new Paragraph({
        children: [new TextRun({ text: "Data Quality Note: Riverbank / Meewasin Tagging Refinement, and Corrected Findings", size: 26, color: "444444" })],
        spacing: { after: 40 },
      }),
      new Paragraph({
        children: [new TextRun({ text: "Ryan Ocampo  \u2022  July 21, 2026  \u2022  Working from saskatoon_safety_* dataset (collection run 2026-06-11)", italics: true, size: 20, color: "666666" })],
        spacing: { after: 320 },
      }),

      h1("Summary"),
      p("The location tagger in the scraper (initial_sraper.py) uses plain substring matching, not word-boundary matching, to detect neighbourhood mentions. The \u201cRiverbank / Meewasin\u201d pattern list includes the bare string \u201criver\u201d, which also matches inside \u201cdriver\u201d and \u201cdrivers.\u201d In a car-safety-heavy subreddit, this produces a very high false-positive rate: 83% of posts and comments tagged Riverbank/Meewasin do not actually mention the river, Meewasin, or the trail at all."),
      p("Once the false positives are removed, the finding that motivated our last round of discussion \u2014 that the Meewasin Trail is the most-mentioned location and carries negative sentiment \u2014 does not hold up. The genuine river/Meewasin subset (8 posts, 114 comments) skews net positive, and the negative comments within it are mostly about park access disputes, winter complaints, and a grass fire, not safety while walking or lighting/isolation concerns."),
      p("Recommendation: fix the tagging regex to use word boundaries, rerun the tagging step across the full dataset (this likely affects other categories too \u2014 e.g. \u201criversdale\u201d also contains \u201criver\u201d as a substring, so Riversdale-tagged posts are probably double-counted under Riverbank/Meewasin as well), and treat the Meewasin/Riverbank case-study framing as unconfirmed until the corrected numbers are in.", { bold: true }),

      h1("1. The issue"),
      p("Location tagging (initial_sraper.py, _tag_neighbourhoods) matches patterns with simple Python \u201cin\u201d containment on lowercased text:"),
      new Paragraph({
        children: [new TextRun({ text: 'if any(p in t for p in patterns): hits.append(name)', font: "Consolas", size: 20 })],
        shading: { type: ShadingType.CLEAR, fill: "F2F2F2" },
        spacing: { after: 160 },
        indent: { left: 200 },
      }),
      p("The Riverbank / Meewasin pattern list is [\"river\", \"meewasin\", \"riverbank\", \"river trail\"]. Because there is no word-boundary check, \u201criver\u201d matches inside any word containing that substring \u2014 most commonly \u201cdriver\u201d / \u201cdrivers,\u201d which are extremely common in a subreddit that discusses traffic and road safety."),

      h2("Scale of the false-positive problem"),
      compareTable(),
      p("Of the 565 false-positive comment matches, 542 (96%) come from the words \u201cdriver\u201d or \u201cdrivers\u201d alone."),

      h1("2. Corrected findings (genuine river/Meewasin mentions only)"),
      p("Applying a word-boundary filter (\\briver\\b, \\bmeewasin\\b, \\briverbank\\b, \\briver trail\\b) to the same posts and comments gives a much smaller, but trustworthy, subset: 8 posts and 114 comments."),
      findingsTable(),
      p("Notably, none of the 8 genuine posts are actually about trail safety perception \u2014 they cover a dog stuck near the river, a coyote sighting, a cat near a bridge, a grass fire nearby, and general apartment/hotel-location questions that happen to reference the river. There is no post in the dataset resembling \u201cis the Meewasin Trail safe at night.\u201d"),

      h1("3. Representative genuine comments"),
      p("A sample of the highest-scored comments in the corrected negative subset (anonymized \u2014 author identifiers were already hashed at collection time, and no usernames are included):"),
      ...quoteBlock("score 34 \u2022 night \u2022 2026-03-23", "There is higher than usual organic content in the river due to runoff from the spring melt. Higher organic content = higher chlorine demand = more smell/taste."),
      ...quoteBlock("score 20 \u2022 evening \u2022 2025-09-10", "It appears that the other 30 km of meewasin is just not enough to satisfy this guy. Gotta have every inch of the waterfront even though they won\u2019t be using the water themselves."),
      ...quoteBlock("score 7 \u2022 evening \u2022 2025-07-19", "What a downright stupid council we elected in this city. Oh, what a great idea, remove the benches so no one can sit down... How about we remove the sidewalks so no one can lay down, or remove the trails by the river..."),
      ...quoteBlock("score 6 \u2022 evening \u2022 2025-09-10", "I have along with other unauthorized modifications to the dirt trails. Every time they deflect and say the riverbank isn\u2019t theirs and to talk to Meewasin. Meewasin says they don\u2019t have the resources and it goes into a black hole."),
      p("These read as park-management and access disputes, not personal-safety accounts. None of the top negative comments in the genuine subset mention lighting, being followed, feeling unsafe, or crime on the trail specifically \u2014 though a small number of lower-scored comments in the 114 do touch on lighting (19 of 114, 16.7%) and it would be worth reading those individually before ruling the theme out entirely.", { italics: true }),

      h1("4. What this means for Varuni's questions"),
      p("Varuni asked (a) what specific reasons drive negative sentiment about Meewasin (lighting, crime, isolation, wildlife, etc.) and (b) what time of day the negative sentiment concentrates at. Based on the corrected data, the honest answer is: the sample of genuine trail-related discussion is too small and too off-topic (park access disputes, not safety) to answer either question with confidence yet. The earlier reply overstated this based on the inflated numbers from the earlier matching approach."),
      p("Suggested path forward:"),
      bullet("Apply word-boundary matching and rerun the full tagging pipeline (affects other neighbourhood categories too, not just Meewasin \u2014 worth a quick audit of all patterns for substring overlap)."),
      bullet("Re-pull the true neighbourhood-mention counts across all 21 tracked areas to see whether Meewasin/Riverbank is still the most-discussed location once corrected \u2014 it may not be."),
      bullet("If the genuine river-mention volume stays this small after the fix, consider whether Meewasin is still the right first case-study site, or whether another neighbourhood has a larger, cleaner signal."),
      bullet("Read through the 114 genuine comments manually (not just top-scored) before drawing conclusions about lighting/isolation/crime themes \u2014 the automated cue tags (lighting, weather, etc.) are keyword-based and may have their own precision issues worth spot-checking."),
    ],
  }],
});

Packer.toBuffer(doc).then(buf => require("fs").writeFileSync("memo.docx", buf));
