import fs from 'fs'

const transcript =
  'C:/Users/JOM/.cursor/projects/c-PROJECTS-zentroapp-webV2/agent-transcripts/fbacb441-ca70-402c-ae18-4d17a83260b8/fbacb441-ca70-402c-ae18-4d17a83260b8.jsonl'
const out =
  'C:/PROJECTS/zentroapp-webV2/frontend/components/dynamic/DynamicDocumentPage.recovered.tsx'

const lines = fs.readFileSync(transcript, 'utf8').split('\n')
let best = ''

for (const line of lines) {
  try {
    const obj = JSON.parse(line)
    for (const c of obj.message?.content ?? []) {
      const s = c.input?.contents ?? c.input?.new_string ?? ''
      if (s.includes('export default function DynamicDocumentPage') && s.length > best.length) {
        best = s
      }
    }
  } catch {
    // ignore
  }
}

if (!best) {
  console.error('No recovery found')
  process.exit(1)
}

fs.writeFileSync(out, best)
console.log('Recovered', best.length, 'chars,', best.split('\n').length, 'lines')
