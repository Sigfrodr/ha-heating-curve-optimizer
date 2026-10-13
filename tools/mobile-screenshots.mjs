// Captures en émulation téléphone réelle (390 px, densité 2) via le protocole DevTools.
// Chrome sans fenêtre ne descend pas sous ~500 px de large : --window-size=390 ne suffit pas à tester le mobile.
// Usage : servir le dépôt sur le port 8777, puis  node tools/mobile-screenshots.mjs <dossier> [onglet,onglet…]
import { spawn } from "node:child_process";
import { writeFileSync, mkdirSync } from "node:fs";
const outDir = process.argv[2];
const tabs = (process.argv[3] || "curve,planning,savings,boiler,diag,settings").split(",");
mkdirSync(outDir, { recursive: true });
const chrome = spawn("C:/Program Files/Google/Chrome/Application/chrome.exe", [
  "--headless=new", "--disable-gpu", "--remote-debugging-port=9336", `--user-data-dir=${process.env.TEMP}\\hco-cdp4`, "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
await sleep(2500);
const targets = await (await fetch("http://127.0.0.1:9336/json")).json();
const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let id = 0;
const send = (method, params) => new Promise((res) => {
  const my = ++id;
  const on = (ev) => { const m = JSON.parse(ev.data); if (m.id === my) { ws.removeEventListener("message", on); res(m.result); } };
  ws.addEventListener("message", on);
  ws.send(JSON.stringify({ id: my, method, params }));
});
await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
for (const tab of tabs) {
  await send("Page.navigate", { url: `http://127.0.0.1:8777/tools/demo/index.html?tab=${tab}&lang=fr` });
  await sleep(3000);
  const m = await send("Runtime.evaluate", { returnByValue: true, expression: `(() => ({ h: document.documentElement.scrollHeight, w: document.documentElement.scrollWidth, vw: innerWidth }))()` });
  const { h, w, vw } = m.result.value;
  const shot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true, clip: { x: 0, y: 0, width: 390, height: Math.min(h, 4000), scale: 1 } });
  writeFileSync(`${outDir}/mob-${tab}.png`, Buffer.from(shot.data, "base64"));
  console.log(tab, `largeur ${w}/${vw}`, `hauteur ${h}`);
}
chrome.kill();
process.exit(0);
