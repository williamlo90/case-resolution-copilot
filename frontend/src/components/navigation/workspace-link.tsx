"use client";

import Link from "next/link";
import { usePracticeSession } from "@/features/practice/context";
import { practiceHref } from "@/features/practice/href";
import {
  useState,
  type ComponentProps,
  type FocusEvent,
  type MouseEvent,
  type TouchEvent,
} from "react";

type WorkspaceLinkProps = Omit<
  ComponentProps<typeof Link>,
  "prefetch"
>;

export function WorkspaceLink({
  onFocus,
  onMouseEnter,
  onTouchStart,
  ...props
}: WorkspaceLinkProps) {
  const practice = usePracticeSession();
  const [intentShown, setIntentShown] = useState(false);

  function handleFocus(event: FocusEvent<HTMLAnchorElement>) {
    setIntentShown(true);
    onFocus?.(event);
  }

  function handleMouseEnter(event: MouseEvent<HTMLAnchorElement>) {
    setIntentShown(true);
    onMouseEnter?.(event);
  }

  function handleTouchStart(event: TouchEvent<HTMLAnchorElement>) {
    setIntentShown(true);
    onTouchStart?.(event);
  }

  return (
    <Link
      {...props}
      href={typeof props.href === "string" ? practiceHref(props.href, practice) : props.href}
      prefetch={intentShown ? null : false}
      onFocus={handleFocus}
      onMouseEnter={handleMouseEnter}
      onTouchStart={handleTouchStart}
    />
  );
}
