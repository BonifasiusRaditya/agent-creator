import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile,FileBlob} from '@oai/artifact-tool';
const dir=new URL('.',import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1');
const file=dir+'TrendForge_Accountability_Sheet.xlsx';
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(file));
const sh=wb.worksheets.getItem('Accountability');
console.log((await wb.inspect({kind:'region',sheetId:'Accountability',range:'B8:C9',maxChars:900})).ndjson);
const before=await wb.render({sheetName:'Accountability',range:'A1:D27',scale:1,format:'png'});
await fs.writeFile(dir+'before-video-update.png',new Uint8Array(await before.arrayBuffer()));
const changes={
 C9:'Product claims use current product-sheet facts and exact evidence quotes. Approved examples guide tone; selected YouTube metadata supplies creative inspiration only. Owned/licensed clips and optional stock supply footage, not new product facts. The creator verifies source facts and footage rights.',
 C13:'Planner selects an angle, Writer produces formats/languages, and Reviewer checks every line. After content approval, Video studio binds that script to 3–5 uploaded clips, approved trim/sequence, FFmpeg rendering, actual faster-whisper transcription, subtitle correction/approval and final MP4 export.',
 C16:'Approved text exports as a ZIP. Video requires the exact approved script, cut and subtitle approvals, and exports as 1080×1920 H.264/AAC MP4 with optional SRT. Source changes invalidate linked release; stale files cannot be released after replacement approval. The creator previews and publishes manually.',
 C19:'Semantic review and speech transcription can make mistakes. Creators must watch the video, check spoken claims and correct subtitles. Certificate verification is a creator attestation, not a registry check. SVG text validation is not OCR. The tested sample uses owned synthetic moving patterns and locally synthesized speech.',
 C22:'101 automated tests passed and 2 dedicated Turso cases skipped in 112.51 seconds. The browser run uploaded 3 speech clips, produced 9 actual ASR cues, saved corrected subtitles and downloaded a real 30.004-second 1080×1920 MP4.',
 C23:'The downloaded MP4 passed a full FFmpeg decode and has H.264 video, AAC stereo 48 kHz, burned-in reviewed subtitles and 30 fps. YouTube returned 20 references; stock search returned 5 clips. db.py connected to Turso. Full video acceptance used isolated SQLite/local storage, not production data.',
 C26:'TrendForge Accountability Sheet; Complete Video Acceptance (1 November 2026); Creator Verification; Challenge C implementation and submission evidence.'
};
for(const [address,text] of Object.entries(changes))sh.getRange(address).values=[[text]];
wb.recalculate();
const after=await wb.render({sheetName:'Accountability',range:'A1:D27',scale:1,format:'png'});
await fs.writeFile(dir+'preview.png',new Uint8Array(await after.arrayBuffer()));
await (await SpreadsheetFile.exportXlsx(wb)).save(file);
console.log('Updated video controls and measured evidence; original layout preserved.');
