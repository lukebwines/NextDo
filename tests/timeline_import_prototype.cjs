// Standalone prototype; not wired into production. Synthetic coordinates only.
// Run: node tests/timeline_import_prototype.cjs
function importTimelinePrototype(data, from, until) {
  const timestamp = value => typeof value === "string" && /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? Date.parse(value) : NaN;
  const lo=timestamp(from), hi=timestamp(until);
  if (!Number.isFinite(lo)||!Number.isFinite(hi)||lo>=hi) throw new Error("Invalid travel period");
  if (!data || !Array.isArray(data.semanticSegments)) throw new Error("Unsupported Android Timeline format");
  const coords=value=>{
    if(typeof value!=="string") return null;
    const m=value.match(/^\s*(-?\d+(?:\.\d+)?)\s*°?\s*,\s*(-?\d+(?:\.\d+)?)\s*°?\s*$/);
    if(!m)return null;
    const lat=Number(m[1]),lon=Number(m[2]);
    return Math.abs(lat)<=90&&Math.abs(lon)<=180?{lat,lon}:null;
  };
  const result={visits:[],activities:[],paths:[]};
  const seen=new Set();
  function add(kind,entry){const key=kind+JSON.stringify(entry);if(!seen.has(key)){seen.add(key);result[kind].push(entry);}}
  for(const s of data.semanticSegments){
    if(!s||typeof s!=="object")continue;
    const start=timestamp(s.startTime),end=timestamp(s.endTime);
    if(!Number.isFinite(start)||!Number.isFinite(end)||end<start||end<lo||start>=hi)continue;
    if(Array.isArray(s.timelinePath)){
      let path=[];
      const flush=()=>{if(path.length)add("paths",path);path=[];};
      for(const p of s.timelinePath){
        const t=timestamp(p?.time), c=coords(p?.point);
        if(!c||!Number.isFinite(t)||t<lo||t>=hi||t<start||t>end){flush();continue;}
        if(path.length&&t<=timestamp(path[path.length-1].time))flush();
        path.push({time:p.time,...c});
      }
      flush();
    }
    // Do not retain boundary-crossing event endpoints or full-event distances.
    if(start<lo||end>=hi)continue;
    const times={startTime:s.startTime,endTime:s.endTime};
    if(s.visit){
      const location=coords(s.visit.topCandidate?.placeLocation?.latLng);
      if(location)add("visits",{...times,location});
    }
    if(s.activity){
      const a=s.activity, first=coords(a.start?.latLng), last=coords(a.end?.latLng);
      if(first&&last){
        const d=a.distanceMeters, mode=a.topCandidate?.type;
        add("activities",{...times,first,last,distanceMeters:typeof d==="number"&&Number.isFinite(d)&&d>=0?d:null,mode:typeof mode==="string"&&/^[A-Z_]{1,60}$/.test(mode)?mode:null});
      }
    }
  }
  return result;
}
function testPrototype(){
 const assert=(condition,message)=>{if(!condition)throw Error(message)};
 const from="2026-01-02T00:00:00-08:00",until="2026-01-03T00:00:00-08:00";
 const visit={startTime:"2026-01-02T08:00:00-08:00",endTime:"2026-01-02T08:30:00-08:00",visit:{topCandidate:{placeLocation:{latLng:"0.1°, 0.2°"},placeId:"PRIVATE"}}};
 const activity={startTime:"2026-01-02T08:30:00-08:00",endTime:"2026-01-02T09:00:00-08:00",activity:{start:{latLng:"0.1°, 0.2°"},end:{latLng:"0.2°, 0.3°"},distanceMeters:1000,topCandidate:{type:"WALKING"}}};
 const path={startTime:"2026-01-01T23:00:00-08:00",endTime:"2026-01-02T10:00:00-08:00",timelinePath:[{point:"1°, 1°",time:"2026-01-01T23:55:00-08:00"},{point:"0.1°, 0.2°",time:"2026-01-02T08:40:00-08:00"},{point:"0.2°, 0.3°",time:"2026-01-02T08:45:00-08:00"}]};
 const outside={...visit,startTime:"2026-01-01T00:00:00-08:00",endTime:"2026-01-01T01:00:00-08:00"};
 const crossing={...activity,startTime:"2026-01-01T23:00:00-08:00"};
 const result=importTimelinePrototype({semanticSegments:[visit,visit,activity,path,outside,crossing],rawSignals:[{secret:"PRIVATE"}],userLocationProfile:{secret:"PRIVATE"}},from,until);
 assert(result.visits.length===1,"visit filtering and dedup");
 assert(result.activities.length===1&&result.activities[0].distanceMeters===1000,"activity filtering");
 assert(result.paths.length===1&&result.paths[0].length===2,"point filtering");
 assert(!JSON.stringify(result).includes("PRIVATE"),"privacy allowlist");
 assert(!JSON.stringify(result).includes("2026-01-01"),"outside period excluded");
 let rejected=false;try{importTimelinePrototype({},from,until)}catch{rejected=true}assert(rejected,"unsupported format rejected");
 return {checks:6,visits:result.visits.length,activities:result.activities.length,points:result.paths[0].length};
}
module.exports={importTimelinePrototype};
if(require.main===module) console.log(testPrototype());
