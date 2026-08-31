const fs = require('fs');
const path = require('path');

// Verify that anomalySpatializer.js has no undefined function calls or broken references
const codePath = path.resolve(__dirname, '../src/cluespace/anomalySpatializer.js');
const code = fs.readFileSync(codePath, 'utf8');

const checks = [
  { name: 'No updatePlayButtonUI call', test: !code.includes('updatePlayButtonUI(') },
  { name: 'No updateTimelineDisplay call', test: !code.includes('updateTimelineDisplay(') },
  { name: 'No buildTimelineMilestones call', test: !code.includes('buildTimelineMilestones(') },
  { name: 'Has buildSatelliteGeometry', test: code.includes('function buildSatelliteGeometry()') },
  { name: 'Has loadInvestigationData', test: code.includes('export async function loadInvestigationData') },
  { name: 'Has startRenderLoop', test: code.includes('function startRenderLoop()') },
  { name: 'Has draw3DScene', test: code.includes('function draw3DScene()') },
  { name: 'No spatializer-bottom-hud in template', test: !code.includes('id="spatializer-bottom-hud"') },
  { name: 'Has 3D canvas in template', test: code.includes('id="spatializer-3d-canvas"') },
  { name: 'Has investigation selector in template', test: code.includes('id="spatializer-sev-filter-group"') || code.includes('spatializer-sev-dropdown') },
  { name: 'Has Channel Inspector in template', test: code.includes('id="spatializer-inspector-card"') },
  { name: 'Has Legend in template', test: code.includes('id="spatializer-legend-card"') },
  { name: 'Has View Controls in template', test: code.includes('id="spatializer-view-controls"') }
];

let allPassed = true;
checks.forEach(c => {
  if (c.test) {
    console.log(`✓ ${c.name}`);
  } else {
    console.error(`✗ FAILED: ${c.name}`);
    allPassed = false;
  }
});

if (allPassed) {
  console.log('\nAll anomalySpatializer static integrity checks passed!');
  process.exit(0);
} else {
  process.exit(1);
}
