const fs = require('fs');
const http = require('http');

function fetchJson(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode, data: JSON.parse(body) });
        } catch (e) {
          resolve({ status: res.statusCode, error: e.message, body });
        }
      });
    }).on('error', reject);
  });
}

async function run() {
  console.log('Testing Investigation Selection & Endpoint Serving:');
  const testIds = ['INV-936', 'INV-988', 'INV-735', 'INV-1', 'INV-805'];

  for (const id of testIds) {
    const url = `http://localhost:5173/data/investigations/${id}.json`;
    try {
      const res = await fetchJson(url);
      if (res.status === 200 && res.data) {
        console.log(`[PASS] ${id}:`);
        console.log(`       - Investigation ID: ${res.data.investigation_id}`);
        console.log(`       - Severity: ${res.data.severity_score} (${res.data.severity_label || res.data.mission_impact_level})`);
        console.log(`       - Significance: ${res.data.significance_score}`);
        console.log(`       - Confidence: ${res.data.investigation_confidence}`);
        console.log(`       - Events: ${res.data.n_events_total}`);
        console.log(`       - Channels: ${(res.data.channel_activation_order || []).join(' -> ')}`);
      } else {
        console.error(`[FAIL] ${id} -> HTTP ${res.status}:`, res.error || 'No data');
      }
    } catch (err) {
      console.log(`[OFFLINE] ${id} -> Dev server not active on port 5173 (${err.code || err.message})`);
    }
  }
}

run();
