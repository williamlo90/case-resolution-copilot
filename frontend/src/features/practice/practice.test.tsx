import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi, beforeEach } from "vitest";
import { practiceHref } from "./href";
import { PracticeLauncher } from "./launcher";
import { createV2Demo } from "@/app/(operations)/_actions/v2-demo";
vi.mock("next/navigation",()=>({useRouter:()=>({push:vi.fn()})}));
vi.mock("@/app/(operations)/_actions/v2-demo",()=>({createV2Demo:vi.fn(),loadV2Demo:vi.fn()}));
const session="VD-1234567890ABCDEF";
beforeEach(()=>vi.clearAllMocks());
it("keeps the practice context only on product workflow links",()=>{
  expect(practiceHref("/cases/CS-1?tab=resolution#history",session)).toBe(`/cases/CS-1?tab=resolution&practice=${session}#history`);
  for(const path of ["/connections","/administration","https://other.example/cases","//other.example/cases"]) expect(practiceHref(path,session)).toBe(path);
  expect(practiceHref("/cases","invalid")).toBe("/cases");
  expect(practiceHref("/cases",null)).toBe("/cases");
});
it("creates nothing on page load and retries failed creation with the same key",async()=>{
  vi.mocked(createV2Demo).mockResolvedValue({data:null,error:"Response interrupted",code:"network"});
  render(<PracticeLauncher sessions={[]}/>);
  expect(createV2Demo).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button",{name:"Try a practice case"}));
  const button=screen.getByRole("button",{name:/Verify and close a refund/});
  fireEvent.click(button);
  await screen.findByRole("alert");
  fireEvent.click(button);
  await waitFor(()=>expect(createV2Demo).toHaveBeenCalledTimes(2));
  expect(vi.mocked(createV2Demo).mock.calls[0][1]).toBe(vi.mocked(createV2Demo).mock.calls[1][1]);
});
