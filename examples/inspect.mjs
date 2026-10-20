// Node 24+. Read-only tool discovery; no credits are spent by this example.
const base = process.env.RECLIP_API_BASE_URL ?? "https://www.reclip.io/api/v1";
if (!process.env.RECLIP_API_KEY) throw new Error("Set RECLIP_API_KEY");
const response = await fetch(`${base}/tools`, {
  headers: { Authorization: `Bearer ${process.env.RECLIP_API_KEY}` },
  redirect: "error",
});
if (!response.ok) throw new Error(`API HTTP ${response.status}`);
console.log(JSON.stringify(await response.json(), null, 2));
