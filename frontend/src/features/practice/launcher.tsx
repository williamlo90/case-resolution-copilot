"use client";
import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { createV2Demo, loadV2Demo } from "@/app/(operations)/_actions/v2-demo";
import { type DemoScenario, type DemoSession } from "@/features/v2-demo/contract";
import { ChevronRight, FlaskConical } from "lucide-react";

const options: {id:DemoScenario; title:string; description:string}[] = [
  {id:"verified_reopen",title:"Verify and close a refund",description:"Check the outcome, close with evidence, then reopen when new information arrives."},
  {id:"sop_revision",title:"When a refund policy changes",description:"See why a previous approval must be reviewed again after the refund limit changes."},
  {id:"timeout_recovery",title:"Recover an interrupted refund",description:"Find the original result without issuing the refund twice."},
];
export function PracticeLauncher({sessions}:{sessions:DemoSession[]}) {
  const [open,setOpen] = useState(false);
  const [error,setError] = useState("");
  const [pending,start] = useTransition();
  const [creation,setCreation] = useState<{scenario:DemoScenario; key:string}|null>(null);
  const router = useRouter();
  function begin(scenario:DemoScenario) {
    const key = creation?.scenario === scenario ? creation.key : crypto.randomUUID();
    setCreation({scenario,key});
    start(async () => {
      setError("");
      const result = await createV2Demo(scenario,key);
      if (!result.data) {setError(result.error ?? "Unable to open the practice case."); return;}
      router.push(`/cases/${result.data.case.id}?practice=${result.data.session.session_id}`);
    });
  }
  function resume(id:string) {
    start(async()=> {
      const result = await loadV2Demo(id);
      if (!result.data) {setError(result.error ?? "Unable to resume."); return;}
      router.push(`/cases/${result.data.case.id}?practice=${id}`);
    });
  }
  return <section className="border-b border-border bg-surface px-4 py-3 sm:px-6 lg:px-7">
    <button onClick={()=>setOpen(!open)} aria-expanded={open} className="inline-flex items-center gap-2 text-sm font-semibold text-info"><FlaskConical size={16}/>Try a practice case</button>
    {open ? <div className="max-w-3xl pb-3 pt-4">
      <p className="mb-4 text-sm leading-6 text-secondary">Use the normal case, review and action screens with isolated sample records. One operator plays the named roles. No real payments or emails.</p>
      <div className="divide-y divide-border border-y border-border">{options.map(o=><button key={o.id} disabled={pending} onClick={()=>begin(o.id)} className="flex w-full items-center justify-between gap-4 py-4 text-left disabled:opacity-50">
        <span><span className="block text-sm font-semibold text-primary">{o.title}</span><span className="mt-1 block text-sm text-secondary">{o.description}</span></span><ChevronRight size={18} className="shrink-0 text-info"/>
      </button>)}</div>
      {sessions.length ? <details className="mt-4"><summary className="cursor-pointer text-sm font-medium text-secondary">Resume a saved practice case</summary><ul className="mt-3 space-y-2">{sessions.map(s=><li key={s.session_id}><button disabled={pending} onClick={()=>resume(s.session_id)} className="text-left text-sm text-info hover:underline">{options.find(o=>o.id===s.scenario)?.title} · {new Date(s.created_at).toLocaleString("en-GB", { timeZone: "UTC" }) + " UTC"}</button></li>)}</ul></details> : null}
      {pending ? <p role="status" className="mt-3 text-sm text-secondary">Opening your isolated case…</p> : null}
      {error ? <p role="alert" className="mt-3 text-sm text-danger">{error} You can retry the same selection.</p> : null}
    </div> : null}
  </section>;
}
