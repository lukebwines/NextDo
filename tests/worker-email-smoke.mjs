/* Check real Cloudflare Worker signing behavior with synthetic MIME data. */
import {strict as assert} from "node:assert";
import {createHmac} from "node:crypto";
import {readFileSync} from "node:fs";
const workerSource=readFileSync("cloudflare/nextdo-email-worker.js","utf8");
const {default:worker}=await import("data:text/javascript;base64,"+
  Buffer.from(workerSource).toString("base64"));
const source=new TextEncoder().encode(
  "From: example@valid.test\r\nTo: scadenze@posta.example.org\r\nSubject: test\r\n\r\nTest email.");
const envelopeFrom="example@valid.test";
const envelopeTo="scadenze@posta.example.org";
const env={
 NEXTDO_ENDPOINT:"https://nextdo.example.org/api/cloudflare-mail/inbound",
 EXPECTED_TO:envelopeTo,ALLOWED_FROM:envelopeFrom,
 NEXTDO_SIGNING_SECRET:"synthetic-secret-no-real-credentials"
};
let requests=0;
globalThis.fetch=async (url,opts)=>{
 requests++;
 assert.equal(url,env.NEXTDO_ENDPOINT);
 assert.equal(opts.method,"POST");
 assert.equal(opts.headers.get("Content-Type"),"message/rfc822");
 const time=opts.headers.get("X-NextDo-Timestamp");
 const sender=opts.headers.get("X-NextDo-Envelope-From");
 const prefix=time+"\n"+sender+"\n"+envelopeTo+"\n";
 const expected=createHmac("sha256",env.NEXTDO_SIGNING_SECRET)
  .update(prefix).update(Buffer.from(opts.body)).digest("hex");
 assert.equal(opts.headers.get("X-NextDo-Signature"),expected);
 assert.deepEqual(Buffer.from(opts.body),Buffer.from(source));
 return {status:202};
};
const mk=(from=envelopeFrom,to=envelopeTo,rawSize=source.length)=>{
 const msg={from,to,rawSize,rejected:"",
 raw:new Blob([source]).stream(),
 setReject(text){this.rejected=text}};
 return msg;
};
await worker.email(mk(),env,{});
assert.equal(requests,1);
const unwanted=mk("untrusted@example.org");
await worker.email(unwanted,env,{});
assert.ok(unwanted.rejected.includes("authorized"));
assert.equal(requests,1);
const tooLarge=mk(envelopeFrom,envelopeTo,7_000_000);
await worker.email(tooLarge,env,{});
assert.ok(tooLarge.rejected.includes("limit"));
assert.equal(requests,1);
const secondSender="another@valid.test";
const multiple={...env,ALLOWED_FROM:envelopeFrom+", "+secondSender.toUpperCase()};
const secondMessage=mk(secondSender);
await worker.email(secondMessage,multiple,{});
assert.equal(secondMessage.rejected,"");
assert.equal(requests,2);
const otherMessage=mk("not"+secondSender);
await worker.email(otherMessage,multiple,{});
assert.ok(otherMessage.rejected.includes("authorized"));
assert.equal(requests,2);
console.log("PASS Cloudflare Worker HMAC, recipient/sender allowlist and 6MB cap");
