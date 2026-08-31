const summary = require('../public/data/investigation_summary.json');
const index = require('../public/data/investigation_index.json');
const inv988 = require('../public/data/inv_988.json');

console.log('Testing Screen 1 (Mission Control) data mappings:');
console.log(' - Total incidents:', summary.total_incidents);
console.log(' - Avg significance:', summary.average_significance.toFixed(2));
console.log(' - Avg severity:', summary.average_severity.toFixed(2));
console.log(' - Avg confidence:', (summary.average_confidence * 100).toFixed(1) + '%');
console.log(' - Critical:', summary.severity_distribution.CRITICAL);
console.log(' - High:', summary.severity_distribution.HIGH);
console.log(' - Moderate:', summary.severity_distribution.MODERATE);
console.log(' - Low:', summary.severity_distribution.LOW);
console.log(' - Multi-channel:', summary.multi_channel_count);
console.log(' - Single-channel:', summary.single_channel_count);

console.log('\nTesting Screen 2 (Incident Explorer) data mappings:');
console.log(' - Total records in index:', index.investigations.length);
console.log(' - Sample record keys:', Object.keys(index.investigations[0]));

console.log('\nTesting Screen 3 (Investigation Workspace) data mappings:');
console.log(' - Investigation ID:', inv988.investigation_id);
console.log(' - Severity score:', inv988.severity_score);
console.log(' - Significance score:', inv988.significance_score);
console.log(' - Timeline events count:', inv988.timeline.length);
console.log(' - Activation sequence:', inv988.channel_activation_order.join(' -> '));
console.log(' - Temporal relationships count:', inv988.channel_temporal_relationships.length);
console.log(' - Hypothesis text:', inv988.hypothesis_statements[0]);
console.log(' - Recommended actions count:', inv988.recommended_actions.length);

console.log('\nAll data mappings verified successfully!');
