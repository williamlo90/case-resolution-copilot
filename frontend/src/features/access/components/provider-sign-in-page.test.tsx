import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { authState, replaceDocumentMock } = vi.hoisted(() => ({
  authState: {
    isLoaded: true,
    isSignedIn: false,
  },
  replaceDocumentMock: vi.fn(),
}));

vi.mock("./full-document-navigation", () => ({
  replaceDocument: replaceDocumentMock,
}));

vi.mock("@clerk/nextjs", () => ({
  SignIn: ({ path }: { path: string }) => (
    <div data-path={path}>Clerk sign in</div>
  ),
  SignUp: ({ path }: { path: string }) => (
    <div data-path={path}>Clerk sign up</div>
  ),
  useAuth: () => authState,
}));

import { SignInPage } from "./sign-in-page";

describe("provider sign-in page", () => {
  beforeEach(() => {
    authState.isLoaded = true;
    authState.isSignedIn = false;
    replaceDocumentMock.mockReset();
  });

  it("mounts Clerk sign-in at its catch-all route base", () => {
    render(<SignInPage providerAuthentication />);

    expect(screen.getByText("Clerk sign in")).toHaveAttribute(
      "data-path",
      "/sign-in",
    );
  });

  it("mounts Clerk sign-up at its catch-all invitation route base", () => {
    render(<SignInPage invite providerAuthentication />);

    expect(screen.getByText("Clerk sign up")).toHaveAttribute(
      "data-path",
      "/invite",
    );
  });

  it("opens the signed-in workspace on the same application origin", async () => {
    authState.isSignedIn = true;

    render(<SignInPage providerAuthentication />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "Opening your workspace",
    );
    await waitFor(() => {
      expect(replaceDocumentMock).toHaveBeenCalledWith("/cases");
    });
  });

  it("offers a manual retry when the authenticated redirect fails", async () => {
    authState.isSignedIn = true;
    replaceDocumentMock
      .mockImplementationOnce(() => {
        throw new Error("navigation failed");
      })
      .mockImplementationOnce(() => undefined);

    render(<SignInPage providerAuthentication />);

    const continueButton = await screen.findByRole("button", {
      name: "Continue",
    });
    fireEvent.click(continueButton);

    await waitFor(() => {
      expect(replaceDocumentMock).toHaveBeenCalledTimes(2);
      expect(replaceDocumentMock).toHaveBeenLastCalledWith("/cases");
    });
  });
});
