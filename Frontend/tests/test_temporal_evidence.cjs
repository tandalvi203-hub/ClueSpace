const inv988 = require('../src/data/investigations/INV-988.json');

console.log('Testing Temporal Evidence presentation mapping for INV-988:');
const rels = inv988.channel_temporal_relationships || [];
console.log('Total relationships:', rels.length);

rels.forEach((rel, i) => {
  let precedenceText = 'Temporal association';
  if (rel.temporal_precedence === 'A_before_B') {
    precedenceText = 'Preceded';
  } else if (rel.temporal_precedence === 'A_after_B' || rel.temporal_precedence === 'B_before_A') {
    precedenceText = 'Followed';
  }

  const overlapText = rel.windows_overlap ? 'Overlapping window' : '';

  console.log(`[${i + 1}] ${rel.channel_a} -> ${rel.channel_b} | Gap: ${rel.temporal_gap_sec} sec | ${precedenceText} | ${overlapText}`);
});
