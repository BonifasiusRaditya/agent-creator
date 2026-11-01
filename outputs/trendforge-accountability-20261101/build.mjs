import fs from 'node:fs/promises';
import {Workbook, SpreadsheetFile} from '@oai/artifact-tool';

const out = new URL('.', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1');
const wb=Workbook.create();
const sh=wb.worksheets.add('Accountability');
sh.showGridLines=false;
sh.tabColor='#FF7A1A';
sh.getRange('A1:D27').format.font={name:'Arial',size:11,color:'#222222'};
sh.getRange('A1:A27').format.columnWidth=3;
sh.getRange('B1:B27').format.columnWidth=24;
sh.getRange('C1:C27').format.columnWidth=108;
sh.getRange('D1:D27').format.columnWidth=3;
sh.getRange('B2').values=[['TrendForge Accountability Sheet']];
sh.getRange('B2').format.font={name:'Arial',size:16,bold:true,color:'#151517'};
sh.getRange('B2:C2').format.rowHeight=29;
sh.getRange('B3:C3').values=[['As of',new Date('2026-11-01T00:00:00Z')]];
sh.getRange('C3').setNumberFormat('dd mmm yyyy');
sh.getRange('B4:C6').values=[
 ['Challenge','Challenge C: The Creator Agent. Tencent Cloud Hackathon Indonesia 2026.'],
 ['Scenario and users','Product launch for beginner creators, marketers and small online sellers.'],
 ['Current engine','Gemini 3.5 Flash-Lite. WorkBuddy connector available; actual WorkBuddy use still needs evidence.']
];
sh.getRange('B3:B6').format.font.bold=true;
sh.getRange('B3:C6').format.rowHeight=24;
sh.getRange('C3:C6').format.wrapText=true;
sh.getRange('B8:C8').values=[['Boundary','Controls and human responsibility']];
sh.getRange('B8:C8').format={fill:'#151517',font:{name:'Arial',size:11,color:'#FFFFFF',bold:true},rowHeight:28,horizontalAlignment:'center',verticalAlignment:'center'};
const controls=[
 ['Sources','Uses the creator’s current product-sheet facts. Factual lines cite a fact ID and exact source quote. Approved examples guide tone only. The creator verifies product facts; this workflow adds no web research or stock-media facts.'],
 ['Untrusted inputs','Source instructions, testimonials, examples and model outputs are treated as data. Testimonials do not establish efficacy. The backend validates schemas and evidence, and the independent Reviewer checks each draft line.'],
 ['Documented rules','FACT_001, CLAIM_001, HALAL_001, AD_001, BRAND_001, LANG_001 and INPUT_001 cover facts, medical claims, halal evidence, advertising, tone, translation and input boundaries. Rejections cite rule IDs. Rules reference the handbook, not an official regulatory certification.'],
 ['Permissions','Project ownership checks apply to every project endpoint. Website changes require a session and CSRF protection. Personal connector tokens are hashed and revocable. Agents receive no provider keys, database credentials, shell access or publishing tools.'],
 ['Agent actions','Planner selects an angle and real source facts. Writer drafts every selected format and language. Reviewer checks all lines and provides cited findings and fixes. Backend safeguards can reject copy even when the model marks it passed.'],
 ['Limits and escalation','Maximum three Writer/Reviewer rounds and an 80-second execution budget. Prohibited medicine requests can stop at Planner for clarification. Invalid results, missing line checks, quota errors, interruptions and unresolved findings escalate without approval.'],
 ['Human approval','A signed-in creator must approve the exact current source and reviewed revision. Editing copy creates a new review; changing the source invalidates release eligibility. Tone-rule proposals need separate human approval. Agents cannot approve or export.'],
 ['Release and covers','Export requires passed review and explicit human approval. ZIP contains text, SVG covers, source/rule snapshots and audit. Cover text is escaped and checked for round-trip consistency. The creator previews and publishes manually; no social account is accessed.'],
 ['Audit and retention','Turso or SQLite stores source/rule snapshots, agent prompts and outputs, rejected drafts, revisions, issues, approval actor/time and export events. Access is owner-scoped. Records remain until project removal; no automatic audit expiry or separate tamper-proof archive exists.'],
 ['External processing','Gemini receives supplied facts, selected drafts, rules and the owner’s approved examples. Free-tier processing may be used by Google to improve products. Use public or fictional facts for demos. Credentials remain in backend .env and are excluded from content exports.'],
 ['Known limitations','Semantic review can miss misleading paraphrases or translation errors. Certificate verification is the creator’s attestation, not a registry check; expired evidence blocks approval/export. SVG text validation is not OCR. The creator checks factual and regulatory claims before publication.']
];
sh.getRange('B9:C19').values=controls;
sh.getRange('B9:C19').format.wrapText=true;
sh.getRange('B9:C19').format.verticalAlignment='top';
sh.getRange('B9:B19').format.font.bold=true;
for(let r=9;r<=19;r++){
 sh.getRange(`B${r}:C${r}`).format.fill=r%2?'#F6F7F9':'#FFFFFF';
 sh.getRange(`B${r}:C${r}`).format.rowHeight=58;
}
sh.getRange('B21:C21').values=[['Verification','Evidence and remaining requirements']];
sh.getRange('B21:C21').format={fill:'#151517',font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},rowHeight:26,horizontalAlignment:'center',verticalAlignment:'center'};
sh.getRange('B22:C24').values=[
 ['Recorded tests','98 automated tests passed; 2 Turso tests skipped because a dedicated test database was not supplied. Tests use synthetic cases and simulated providers. Real Gemini produced two formats in three languages in 10.67 seconds; a forced claim rejection and repair took 13.44 seconds.'],
 ['Observed safeguards','Real medical-claim edit was rejected and repaired. Export was blocked before website approval. A request to label a herbal product “obat maag” escalated with CLAIM_001 in 1.83 seconds. These are individual local observations, not performance guarantees.'],
 ['Evidence still needed','Actual WorkBuddy execution, official organizer dataset/rulebook and cases, recorded 5–8 minute demo, and public source or an exported WorkBuddy workflow with evidence. Connector installation and Gemini tests do not establish actual WorkBuddy use.']
];
sh.getRange('B22:C24').format.wrapText=true;
sh.getRange('B22:C24').format.verticalAlignment='top';
sh.getRange('B22:C24').format.rowHeight=58;
sh.getRange('B22:B24').format.font.bold=true;
sh.getRange('B24:C24').format.fill='#FFF0E4';
sh.getRange('B26:C27').values=[
 ['Source references','TrendForge Accountability Sheet; Creator Verification (1 November 2026); Challenge C implementation and submission evidence.'],
 ['Handbook basis','Tencent Cloud Hackathon Indonesia 2026 handbook: Challenge C, pp. 8–9; data/testing, p. 10; submission requirements, pp. 11–12. Official fictional-company rulebook and cases were not provided.']
];
sh.getRange('B26:C27').format.wrapText=true;
sh.getRange('B26:C27').format.verticalAlignment='top';
sh.getRange('B26:C27').format.rowHeight=40;
sh.getRange('B26:B27').format.font.bold=true;
sh.getRange('B26:C27').format.font.color='#5A5A5A';
sh.freezePanes.freezeRows(8);
wb.recalculate();
console.log((await wb.inspect({kind:'region',sheetId:'Accountability',range:'B8:C10',maxChars:1400,tableMaxRows:3,tableMaxCols:2})).ndjson);
const preview=await wb.render({sheetName:'Accountability',range:'A1:D27',scale:1,format:'png'});
await fs.writeFile(out+'preview.png',new Uint8Array(await preview.arrayBuffer()));
await (await SpreadsheetFile.exportXlsx(wb)).save(out+'TrendForge_Accountability_Sheet.xlsx');
console.log('Saved TrendForge_Accountability_Sheet.xlsx');
