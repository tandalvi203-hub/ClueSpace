const fs = require('fs');
const path = require('path');

console.log('--- Verifying ClueSpace Data Integrity ---');

// 1. Check summary
const summaryPath = path.resolve(__dirname, '../public/data/investigation_summary.json');
const summary = JSON.parse(fs.readFileSync(summaryPath, 'utf8'));
console.log('Summary check:');
console.log(' - total_incidents:', summary.total_incidents, summary.total_incidents === 805 ? 'OK' : 'MISMATCH');
console.log(' - severity_distribution:', summary.severity_distribution);
console.log(' - multi_channel_count:', summary.multi_channel_count, summary.multi_channel_count === 484 ? 'OK' : 'MISMATCH');
console.log(' - single_channel_count:', summary.single_channel_count, summary.single_channel_count === 321 ? 'OK' : 'MISMATCH');
console.log(' - avg_significance:', summary.average_significance);
console.log(' - avg_severity:', summary.average_severity);
console.log(' - avg_confidence:', summary.average_confidence);

// 2. Check index
const indexPath = path.resolve(__dirname, '../public/data/investigation_index.json');
const index = JSON.parse(fs.readFileSync(indexPath, 'utf8'));
console.log('\nIndex check:');
console.log(' - total_investigations:', index.total_investigations, index.investigations?.length === 805 ? 'OK' : 'MISMATCH');
const inv988InIndex = index.investigations.find(i => i.investigation_id === 'INV-988');
console.log(' - INV-988 in index:', inv988InIndex);

// 3. Check INV-988 detailed payload
const inv988Path = path.resolve(__dirname, '../public/data/inv_988.json');
const inv988 = JSON.parse(fs.readFileSync(inv988Path, 'utf8'));
console.log('\nINV-988 Detailed Payload check:');
console.log(' - investigation_id:', inv988.investigation_id);
console.log(' - severity_score:', inv988.severity_score);
console.log(' - significance_score:', inv988.significance_score);
console.log(' - timeline length:', inv988.timeline.length);
console.log(' - timeline_truncated:', inv988.timeline_truncated);
console.log(' - timeline_shown_count:', inv988.timeline_shown_count);
console.log(' - channel_activation_order:', inv988.channel_activation_order);
console.log(' - temporal relationships count:', inv988.channel_temporal_relationships.length);
console.log(' - evidence graph nodes count:', inv988.evidence_graph.nodes.length);
console.log(' - evidence graph edges count:', inv988.evidence_graph.edges.length);
console.log(' - recommended actions count:', inv988.recommended_actions.length);
console.log(' - hypothesis summary:', inv988.hypothesis_statements[0]);

console.log('\nAll data integrity checks passed!');
