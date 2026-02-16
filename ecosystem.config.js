module.exports = {
  apps: [
    {
      name: "x-rapor-python",
      script: "app.py",
      interpreter: "./venv/bin/python3",
      output: "./logs/python_out.log",
      error: "./logs/python_error.log",
    },
    {
      name: "x-rapor-node",
      script: "server.js",
      cwd: "./x-screenshot-araci",
      output: "../logs/node_out.log",
      error: "../logs/node_error.log",
    },
  ],
};
