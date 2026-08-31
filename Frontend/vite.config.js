import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    host: '0.0.0.0',
    port: 5173,
    watch: {
      usePolling: true,
      interval: 1000,
      ignored: [
        '**/enhanced_landingpage_frames/**',
        '**/landingpage/**',
        '**/ezgif-2cf3e10c63d881f2-jpg/**',
        '**/*.jpg',
        '**/*.jpeg',
        '**/*.png',
        '**/*.zip',
        '**/*.json',
        '**/*.mp4',
        '**/*.raw',
        '**/*.tmp'
      ]
    }
  }
});
