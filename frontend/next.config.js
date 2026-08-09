/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    domains: ['localhost'],
  },
  // 启用 WebSocket 代理
  async headers() {
    return [
      {
        source: '/ws/:path*',
        headers: [
          { key: 'Upgrade', value: 'websocket' },
          { key: 'Connection', value: 'Upgrade' },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
