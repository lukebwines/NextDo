/**
 * Cloudflare Email Routing -> NextDo.
 * Connect the Email Routing address to this Worker in the Cloudflare dashboard.
 * Configure NEXTDO_ENDPOINT, EXPECTED_TO, ALLOWED_FROM as text variables.
 * Configure NEXTDO_SIGNING_SECRET as an encrypted Worker secret.
 * If Cloudflare Access protects the endpoint, also configure CF_ACCESS_CLIENT_ID
 * and CF_ACCESS_CLIENT_SECRET as Worker secrets and authorize a Service Auth policy.
 */
const LIMIT_BYTES = 6_000_000;

function hex(buffer) {
  return Array.from(new Uint8Array(buffer), x => x.toString(16).padStart(2, "0")).join("");
}

async function sign(secret, timestamp, sender, recipient, raw) {
  const encoder = new TextEncoder();
  const prefix = encoder.encode(timestamp + "\n" + sender + "\n" + recipient + "\n");
  const bytes = new Uint8Array(prefix.length + raw.byteLength);
  bytes.set(prefix, 0);
  bytes.set(new Uint8Array(raw), prefix.length);
  const key = await crypto.subtle.importKey(
    "raw", encoder.encode(secret), {name: "HMAC", hash: "SHA-256"}, false, ["sign"]);
  return hex(await crypto.subtle.sign("HMAC", key, bytes));
}

export default {
  async email(message, env, ctx) {
    const sender = (message.from || "").trim().toLowerCase();
    const recipient = (message.to || "").trim().toLowerCase();
    const expected = (env.EXPECTED_TO || "").trim().toLowerCase();
    const allowed = (env.ALLOWED_FROM || "").split(",")
      .map(address => address.trim().toLowerCase()).filter(Boolean);

    // Fail closed: do not process incoming mail before configuration is complete.
    if (!expected || !allowed.length || !env.NEXTDO_SIGNING_SECRET || !env.NEXTDO_ENDPOINT) {
      throw new Error("NextDo email Worker is not configured");
    }
    if (recipient !== expected || !allowed.includes(sender)) {
      message.setReject("This mailbox only accepts authorized forwarded messages");
      return;
    }
    if (message.rawSize > LIMIT_BYTES) {
      message.setReject("Message exceeds the NextDo 6MB limit");
      return;
    }

    const target = new URL(env.NEXTDO_ENDPOINT);
    if (target.protocol !== "https:" || target.pathname !== "/api/cloudflare-mail/inbound" ||
        target.username || target.password || target.search || target.hash) {
      throw new Error("Invalid NextDo ingest URL");
    }

    const raw = await new Response(message.raw).arrayBuffer();
    if (!raw.byteLength || raw.byteLength > LIMIT_BYTES) {
      message.setReject("Message is empty or exceeds NextDo size limits");
      return;
    }

    const timestamp = String(Math.floor(Date.now() / 1000));
    const signature = await sign(env.NEXTDO_SIGNING_SECRET, timestamp, sender, recipient, raw);
    const headers = new Headers({
      "Content-Type": "message/rfc822",
      "X-NextDo-Timestamp": timestamp,
      "X-NextDo-Signature": signature,
      "X-NextDo-Envelope-From": sender,
      "X-NextDo-Envelope-To": recipient,
    });

    // Optional service-to-service authentication when Cloudflare Access is enabled.
    if (env.CF_ACCESS_CLIENT_ID && env.CF_ACCESS_CLIENT_SECRET) {
      headers.set("CF-Access-Client-Id", env.CF_ACCESS_CLIENT_ID);
      headers.set("CF-Access-Client-Secret", env.CF_ACCESS_CLIENT_SECRET);
    }

    const result = await fetch(target.toString(), {method: "POST", headers, body: raw});
    if (result.status !== 202) {
      // Do not log raw email, signature, tokens, or provider response bodies.
      throw new Error("NextDo did not acknowledge inbound message, HTTP " + result.status);
    }
  },
};
