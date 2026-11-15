/**
 * 07_build_august_report_docx.js
 * ================================
 * CPTED Vision | Builds the full August progress report
 *
 * PURPOSE
 * Generates CPTED_Vision_August_Report.docx: the main deliverable,
 * combining the corrected analysis (02_corrected_analysis.py), the
 * charts (03_generate_charts.py), and the example quotes
 * (05_extract_example_quotes.py) into one report with narrative,
 * tables, and embedded figures.
 *
 * INPUT
 *   Reads chart PNGs from the current directory (chart1..chart6, copy
 *   them from output/ first, see run_all.sh). Narrative text and the
 *   specific numbers quoted in it are hardcoded from the analysis run
 *   at the time this report was written -- if you re-run the pipeline
 *   with new data, update the numbers in this file to match.
 *
 * OUTPUT
 *   august_report.docx
 *
 * USAGE
 *   npm install docx   (if not already installed)
 *   node 07_build_august_report_docx.js
 */

const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle, ImageRun, PageBreak
} = require("docx");
const fs = require("fs");

const PAGE_W = 12240, PAGE_H = 15840;
const NAVY = "1F3B5C";

function h1(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_1, spacing: { before: 320, after: 140 } });
}
function h2(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_2, spacing: { before: 220, after: 100 } });
}
function p(text, opts = {}) {
  return new Paragraph({ children: [new TextRun({ text, ...opts })], spacing: { after: 160 } });
}
function bullet(text, opts = {}) {
  return new Paragraph({ children: [new TextRun({ text, ...opts })], bullet: { level: 0 }, spacing: { after: 80 } });
}
function quoteBlock(meta, text) {
  return [
    new Paragraph({ children: [new TextRun({ text: meta, italics: true, size: 18, color: "666666" })], spacing: { before: 120, after: 40 } }),
    new Paragraph({
      children: [new TextRun({ text: `"${text}"`, size: 20 })],
      indent: { left: 360 },
      border: { left: { style: BorderStyle.SINGLE, size: 12, color: "999999", space: 8 } },
      spacing: { after: 160 },
    }),
  ];
}
function img(path, width, height, caption) {
  const data = fs.readFileSync(path);
  const scale = 560 / width; // target ~560px display width in docx units (roughly 5.8in)
  const out = [
    new Paragraph({
      children: [new ImageRun({ data, transformation: { width: Math.round(width*scale*0.75), height: Math.round(height*scale*0.75) } })],
      spacing: { before: 120, after: 60 },
    }),
  ];
  if (caption) {
    out.push(new Paragraph({
      children: [new TextRun({ text: caption, italics: true, size: 18, color: "666666" })],
      spacing: { after: 200 },
    }));
  }
  return out;
}
function cell(text, opts = {}) {
  return new TableCell({
    width: { size: opts.width || 2000, type: WidthType.DXA },
    shading: opts.header ? { type: ShadingType.CLEAR, fill: NAVY } : undefined,
    margins: { top: 70, bottom: 70, left: 90, right: 90 },
    children: [new Paragraph({
      children: [new TextRun({ text, bold: !!opts.header, color: opts.header ? "FFFFFF" : "000000", size: 19 })],
    })],
  });
}
function table(headerRow, dataRows, colW) {
  const header = new TableRow({ children: headerRow.map((t,i) => cell(t, { width: colW[i], header: true })) });
  const rows = dataRows.map(r => new TableRow({ children: r.map((t,i) => cell(String(t), { width: colW[i] })) }));
  return new Table({ width: { size: colW.reduce((a,b)=>a+b,0), type: WidthType.DXA }, columnWidths: colW, rows: [header, ...rows] });
}

const doc = new Document({
  sections: [{
    properties: { page: { size: { width: PAGE_W, height: PAGE_H }, margin: { top: 1080, bottom: 1080, left: 1260, right: 1260 } } },
    children: [
      new Paragraph({ children: [new TextRun({ text: "CPTED Vision", bold: true, size: 44, color: NAVY })], spacing: { after: 40 } }),
      new Paragraph({ children: [new TextRun({ text: "Reddit Safety-Perception Analysis \u2014 August Progress Report", size: 28, color: "444444" })], spacing: { after: 40 } }),
      new Paragraph({ children: [new TextRun({ text: "Prepared by Ryan Ocampo  \u2022  July 21, 2026  \u2022  For discussion with Dr. Kang and Dr. Jayasooriya, August meeting", italics: true, size: 20, color: "666666" })], spacing: { after: 320 } }),

      h1("Executive Summary"),
      p("This report corrects a location-tagging issue identified in the June 2026 Reddit collection, then re-runs the full neighbourhood, sentiment, environmental-cue, and temporal analysis on the corrected data. It is meant to give us a solid, verified foundation for the August meeting \u2014 specifically for deciding on Phase 1 case-study site(s), the environmental parameters worth sensing, and how to frame the next round of the ethics-application conversation."),
      p("Headline change from what I described in my July 20 email: once the tagging is refined, Downtown/CBD \u2014 not the Meewasin Trail \u2014 is the most-mentioned location in the dataset by a wide margin (320 corrected mentions vs. 122), and it is also the most negative high-volume site (40.3% of its comments are negative, mean sentiment near-neutral at +0.06, and its only negative time-of-day bucket is night). Riverbank/Meewasin, once corrected, is a smaller and net-positive signal (mean sentiment +0.33, 22.1% negative)."),
      p("This doesn't mean Meewasin is off the table, it means the case for it needs to rest on the literature review and the sensor-deployment logic, not on a Reddit negative-sentiment claim that the corrected data doesn't actually support as strongly as I first suggested."),

      h1("1. Context"),
      p("Per the July 20 email thread: the ethics application is on hold until we have a firmer sense of the sensor data and collection strategy (Dr. Kang, Dr. Jayasooriya). Dr. Kang also flagged that we need to think carefully about selection biases in the Reddit data before leaning on it. Dr. Jayasooriya asked two specific questions about the Meewasin finding I reported \u2014 what specific factors (lighting, crime, isolation, wildlife) drive the negative sentiment there, and what time of day it concentrates at \u2014 and treated the Meewasin negative-sentiment finding as a settled justification for selecting it as the first case-study site."),
      p("While preparing detailed answers to those questions, I found that the location-tagging step had a location-matching issue that was inflating the Meewasin count specifically (detailed in Section 2). Correcting it changes the site-selection picture enough that I think it's worth walking through properly before the meeting, rather than answering the original questions on data I now know is unreliable."),

      h1("2. Data quality correction"),
      p("The neighbourhood tagger (initial_sraper.py) matches location keywords with plain substring containment (\u201cp in t\u201d), not word-boundary matching. I audited all 20 tracked neighbourhood categories against this issue by comparing raw substring matches to word-boundary-corrected matches. The problem turned out to be isolated almost entirely to one category:"),
      ...img("chart1_raw_vs_corrected.png", 1800, 840, "Figure 1. Raw vs. corrected mention counts for the six priority-tagged sites. Riverbank/Meewasin is the only category materially affected."),
      p("Riverbank/Meewasin used the bare pattern \u201criver\u201d, which also matches inside \u201cdriver\u201d and \u201cdrivers.\u201d That accounts for 542 of 565 false-positive comment matches (96%). The other five priority categories (Pleasant Hill, Riversdale, Downtown/CBD, Downtown Terminal, Confederation Mall) show 0\u20132% false-positive rates and did not need correction."),
      p("One secondary caveat worth noting for Downtown/CBD specifically: \u201cdowntown\u201d is a generic term, and a small number of matched comments turn out to be about the downtown of a different city (raised as a comparison point in a thread), not Saskatoon's. This doesn't come close to the scale of the river/driver issue, but it's worth spot-checking before we treat every Downtown/CBD-tagged comment as literally about Saskatoon.", { italics: true }),

      h1("3. Corrected citywide findings"),
      ...img("chart2_corrected_volume.png", 1800, 900, "Figure 2. Corrected total mentions (posts + comments) by neighbourhood, sites with 15+ mentions."),
      ...img("chart3_sentiment_by_site.png", 1800, 900, "Figure 3. Mean sentiment and % negative by site, corrected. Downtown/CBD is the most negative high-volume site."),
      p("The corrected ranking reshuffles the case-study conversation. Downtown/CBD is both the highest-volume site (320 mentions) and the most negative among high-volume sites. Market Mall and Lakeridge show higher negative percentages still, but on very small samples (n=4 and n=11) that shouldn't be read as strong signals yet."),

      h1("4. Site deep dive: Downtown / CBD"),
      p("With the corrected tagging, Downtown/CBD is the strongest, most robust signal in the dataset: 320 total mentions, 40.3% negative, mean sentiment +0.06 (essentially neutral, dragged down from more positive by a sizeable negative cluster)."),
      ...img("chart5_time_of_day.png", 1600, 860, "Figure 4. Mean sentiment by time of day, Downtown/CBD vs. Riverbank/Meewasin. Downtown/CBD is the only site with a negative average time bucket (night)."),
      p("Downtown/CBD is flat-to-slightly-positive through morning, afternoon, and evening, and dips negative specifically at night (mean -0.004, n=40). The recurring themes in the negative comments are less about the physical environment (lighting, weather) and more about perceived social/behavioural conditions: encounters with visibly unwell or unhoused people, drug paraphernalia in semi-public spaces, and a general sense of avoidance (\"I avoid downtown as much as possible\"). A sample, anonymized:"),
      ...quoteBlock("score 40 \u2022 afternoon", "It's on a block that if you listened to a specific type of person would be more dangerous to walk down than hell already... most businesses do not care about the communities they are in."),
      ...quoteBlock("score 39 \u2022 afternoon", "We've had to lock all washrooms and give tenants keys to give to their clientele in buildings that aren't on lockdown. Otherwise we walk into washrooms with blood all over the walls and mirrors, various used drug paraphernalia lying around, feces on the floors."),
      ...quoteBlock("score 25 \u2022 afternoon", "Neither the municipal nor provincial governments are taking effective action... I avoid downtown as much as possible for the reasons in the article and I still see clusters of street people."),
      p("This reads closer to a narrative-criminology story about visible poverty, addiction, and disorder than an environmental-design story about lighting or physical layout \u2014 worth flagging since it changes what a CPTED/sensor intervention could realistically address here."),

      h1("5. Site deep dive: Riverbank / Meewasin (corrected)"),
      p("Corrected to genuine mentions, Meewasin is a much smaller signal than reported: 8 posts, 114 comments, mean sentiment +0.33 (net positive), 22.1% negative. It peaks positive in the morning (+0.50) and dips \u2014 but stays positive \u2014 in the evening (+0.14)."),
      p("The negative comments within this set skew toward park-management and access disputes (trail modification complaints, jurisdiction disputes between the city and Meewasin Valley Authority) rather than personal-safety accounts. A sample, anonymized:"),
      ...quoteBlock("score 20 \u2022 evening", "It appears that the other 30 km of meewasin is just not enough to satisfy this guy. Gotta have every inch of the waterfront even though they won\u2019t be using the water themselves."),
      ...quoteBlock("score 6 \u2022 evening", "I have along with other unauthorized modifications to the dirt trails. Every time they deflect and say the riverbank isn\u2019t theirs and to talk to Meewasin. Meewasin says they don\u2019t have the resources and it goes into a black hole."),
      ...quoteBlock("score 35 \u2022 evening (positive example, for balance)", "I was downtown yesterday evening and was happily surprised by how vibrant things seemed... I can go for a run or a walk along the river so easily."),
      p("Lighting, weather, and \u201ctime of day\u201d language still show up in Meewasin's negative comments at broadly similar rates to Downtown/CBD's (Figure 5), but on a much smaller base (26 negative comments vs. 118), so these percentages should be read as suggestive, not conclusive."),
      ...img("chart4_env_cues.png", 1800, 900, "Figure 5. Environmental-cue co-occurrence within negative comments, citywide vs. Downtown/CBD vs. Riverbank/Meewasin (corrected)."),

      h1("6. Temporal patterns, citywide"),
      ...img("chart6_seasonal.png", 1600, 800, "Figure 6. Post volume and mean sentiment by season, all posts."),
      p("Sentiment is most positive in spring (+0.32) and least positive in fall (+0.17), with summer carrying the highest post volume (126). This is a broad seasonal pattern, not something to over-read site by site given the smaller per-site, per-season sample sizes."),

      h1("7. Answering Dr. Jayasooriya's questions"),
      p("With the corrected data, here's a direct answer to what she asked:"),
      bullet("Specific reasons for negative sentiment: this now depends heavily on which site. For Downtown/CBD (the strongest signal), the negative sentiment is driven mainly by social/behavioural cues (drug use, visible homelessness, perceived crime) rather than physical-environment cues like lighting. For Meewasin, the environmental cues she named (lighting ~15%, weather ~27%) appear in the negative subset, but the subset itself is small and much of it isn't really about personal safety."),
      bullet("Time of day: for Downtown/CBD, negative sentiment concentrates specifically at night. For Meewasin, there isn't a strong time-of-day negative concentration \u2014 sentiment is positive throughout, just less positive in the evening."),
      bullet("On the \u201cstrong justification\u201d framing: the data now supports Downtown/CBD as the site with a strong, robust Reddit safety-perception signal. Meewasin's signal is real in the literature-review sense (it's an under-studied gap) but not in the \u201cReddit shows strong negative sentiment\u201d sense I described in my first email."),

      h1("8. Methodological limitations / selection bias"),
      p("In response to Dr. Kang's note about selection biases, worth naming explicitly before the meeting:"),
      bullet("Platform skew: r/saskatoon users are self-selected toward younger, English-speaking, internet-active residents; this likely under-represents groups without reliable internet access or English fluency, and over-represents students, downtown workers, and drivers."),
      bullet("Seed-term framing: the 12 safety/danger seed terms shape which posts got captured in the first place \u2014 we're seeing where people already framed something as a safety topic, not a neutral sample of all neighbourhood discussion."),
      bullet("Volume \u2260 danger: Downtown/CBD's high mention count partly reflects that it's simply where more people go and post about, not necessarily that it's proportionally more dangerous per visit."),
      bullet("The \u201cdowntown\u201d generic-term issue noted in Section 2, and the matching issue this whole report is built around, are both reminders that every neighbourhood tag in this pipeline should be spot-checked by hand before being cited as a finding, not just trusted from the aggregate count."),
      bullet("This also intersects with the anti-stigma tension already flagged in the lit review (Wacquant, Schwarze): leaning on crime/negative-sentiment data to justify targeting a neighbourhood for surveillance-adjacent sensing risks reproducing the same stigmatizing framing the lit review argues against, worth being explicit about this trade-off if Downtown/CBD is proposed as a site given its concentration of unhoused/addiction-related commentary."),

      h1("9. Recommendation for case-study site selection"),
      p("Given the corrected data, the budget/scope conversation we've had before (roughly 8 candidate sites vs. an exploratory-grant-scale project), and the stigma tension above, I'd suggest going into August with two options on the table rather than a single answer:"),
      bullet("Option A \u2014 Downtown/CBD as the primary Phase 1 site: strongest, most robust Reddit signal; but requires an explicit plan for how we frame findings about homelessness/addiction without reproducing stigma, and what sensor parameters would even be responsive to socially-driven (not environmentally-driven) negative sentiment."),
      bullet("Option B \u2014 Meewasin as a secondary/comparison site: weaker Reddit signal than initially reported, but still justified by the literature-review gap (it's genuinely understudied) and by its relevance to the lighting/physical-design sensor pillar, since its (smaller) negative cluster is more classically CPTED-shaped."),
      bullet("Either way, I'd recommend scoping to 2\u20133 Phase 1 sites rather than the full candidate list, consistent with the exploratory scale of the current grant."),

      h1("10. Proposed agenda items for the August meeting"),
      bullet("Confirm Phase 1 site(s) using the corrected data above, and agree on the stigma-framing approach if Downtown/CBD is included."),
      bullet("Decide which environmental parameters the sensor deployment should prioritize per site, physical (lighting, noise, weather) for Meewasin, and discuss what a sensor pillar even measures for Downtown/CBD's more social/behavioural signal."),
      bullet("Revisit ethics-application strategy now that we have a clearer, corrected picture of what the Reddit data can and can't support."),
      bullet("Agree on next data step: spot-check the \u201cdowntown\u201d generic-term issue, and consider whether any other categories need manual review before being used in the paper draft."),

      h1("Appendix: files accompanying this report"),
      bullet("CPTED_Vision_August_DataTables.xlsx \u2014 full corrected data tables (neighbourhood summary, raw-vs-corrected comparison, environmental cues by site, time-of-day by site, seasonal trend)."),
      bullet("CPTED_Vision_Meewasin_DataQuality_Memo.docx \u2014 earlier, narrower memo focused specifically on the Meewasin matching issue (superseded in scope by this report, kept for reference)."),
      bullet("Charts (Figures 1\u20136 above) are also included as standalone PNG files for reuse in slides or the paper draft."),
    ],
  }],
});

Packer.toBuffer(doc).then(buf => fs.writeFileSync("august_report.docx", buf));
