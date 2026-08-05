import type { LucideIcon } from "lucide-react";
import { useRef, type KeyboardEvent } from "react";

export type WorkspaceTabItem<T extends string> = {
  id: T;
  label: string;
  icon: LucideIcon;
};

export function WorkspaceTabs<T extends string>({
  items,
  activeTab,
  onTabChange,
  label,
  panelIdPrefix,
}: {
  items: readonly WorkspaceTabItem<T>[];
  activeTab: T;
  onTabChange: (tab: T) => void;
  label: string;
  panelIdPrefix: string;
}) {
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

  function selectByKeyboard(
    event: KeyboardEvent<HTMLButtonElement>,
    currentIndex: number,
  ) {
    const lastIndex = items.length - 1;
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % items.length;
    if (event.key === "ArrowLeft") {
      nextIndex = (currentIndex - 1 + items.length) % items.length;
    }
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = lastIndex;
    if (nextIndex === null) return;

    event.preventDefault();
    const nextTab = items[nextIndex];
    if (!nextTab) return;
    onTabChange(nextTab.id);
    tabRefs.current[nextIndex]?.focus();
  }

  return (
    <div role="tablist" aria-label={label} className="flex gap-1 overflow-x-auto">
      {items.map((tab, index) => {
        const Icon = tab.icon;
        const active = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            ref={(element) => {
              tabRefs.current[index] = element;
            }}
            id={`${panelIdPrefix}-tab-${tab.id}`}
            type="button"
            role="tab"
            aria-selected={active}
            aria-controls={`${panelIdPrefix}-${tab.id}`}
            tabIndex={active ? 0 : -1}
            onClick={() => onTabChange(tab.id)}
            onKeyDown={(event) => selectByKeyboard(event, index)}
            className={`relative flex h-12 min-w-max items-center gap-2 px-3 text-sm font-medium transition-colors ${active ? "text-primary" : "text-secondary hover:text-primary"}`}
          >
            <Icon aria-hidden="true" size={16} />
            {tab.label}
            {active ? <span className="absolute inset-x-2 bottom-0 h-0.5 bg-action" /> : null}
          </button>
        );
      })}
    </div>
  );
}
