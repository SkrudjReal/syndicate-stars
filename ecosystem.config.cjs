const path = require('node:path');
module.exports = {
  apps: [
    { name: 'syndicate-stars', args: '-m bot' },
    { name: 'payment-notifications', args: '-m bot.notifications' },
  ].map(app => ({
    ...app,
    script: path.join(__dirname, '.venv/bin/python'),
    interpreter: 'none',
    cwd: __dirname,
    instances: 1,
    autorestart: true,
    restart_delay: 5000,
    kill_timeout: 20000,
    max_memory_restart: '450M',
    env: { PYTHONUNBUFFERED: '1' },
    out_file: path.join(__dirname, 'logs', `${app.name}.out.log`),
    error_file: path.join(__dirname, 'logs', `${app.name}.err.log`),
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
  })),
};
