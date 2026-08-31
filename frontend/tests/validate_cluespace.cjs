const http = require('http');

function checkUrl(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => resolve({ status: res.statusCode, length: body.length }));
    }).on('error', reject);
  });
}

async function run() {
  console.log('Testing server endpoints:');
  const urls = [
    'http://localhost:5173/',
    'http://localhost:5173/data/investigation_summary.json',
    'http://localhost:5173/data/investigation_index.json',
    'http://localhost:5173/data/inv_988.json',
    'http://localhost:5173/src/cluespace/cluespace.css',
    'http://localhost:5173/src/cluespace/cluespace_app.js',
    'http://localhost:5173/src/cluespace/navigation.js',
    'http://localhost:5173/src/cluespace/screen1_mission_control.js',
    'http://localhost:5173/src/cluespace/screen2_incident_explorer.js',
    'http://localhost:5173/src/cluespace/screen3_investigation_workspace.js',
    'http://localhost:5173/src/cluespace/screen4_watsonx_brief.js'
  ];

  let passed = 0;
  for (const u of urls) {
    try {
      const res = await checkUrl(u);
      if (res.status === 200) {
        console.log(`[PASS] ${u} -> HTTP ${res.status} (${res.length} bytes)`);
        passed++;
      } else {
        console.error(`[FAIL] ${u} -> HTTP ${res.status}`);
      }
    } catch (e) {
      console.error(`[FAIL] ${u} -> ${e.message}`);
    }
  }

  console.log(`\nEndpoint verification summary: ${passed}/${urls.length} passed.`);
}

run();
