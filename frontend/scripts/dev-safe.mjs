import { spawn } from "node:child_process";
import path from "node:path";

if (process.env.SUPPORT_COPILOT_ALLOW_LOCAL_DEV !== "1") {
  console.error(
    "BLOCKED: local Next.js development needs about 1 GB of RAM on this project. " +
      "Use a hosted preview, or set SUPPORT_COPILOT_ALLOW_LOCAL_DEV=1 only after explicit approval.",
  );
  process.exit(1);
}

const nextCli = path.join(
  process.cwd(),
  "node_modules",
  "next",
  "dist",
  "bin",
  "next",
);
const child = spawn(
  process.execPath,
  [
    nextCli,
    "dev",
    "--webpack",
    "--hostname",
    "localhost",
    ...process.argv.slice(2),
  ],
  {
    env: {
      ...process.env,
      NODE_OPTIONS: "--max-old-space-size=512",
    },
    stdio: "inherit",
  },
);

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => {
    child.kill(signal);
  });
}

child.on("error", (error) => {
  console.error(`Unable to start the low-memory Next.js server: ${error.message}`);
  process.exitCode = 1;
});

child.on("exit", (code, signal) => {
  process.exitCode = signal ? 1 : (code ?? 1);
});
