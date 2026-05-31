/**
 * Wave 2 motion primitives — reduced-motion gating (AC2.4), count-up payoff
 * (AC2.1), and the 250ms hover-intent used by the pyramid ghost card (AC2.2).
 */
import { act, render, renderHook, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CountUp, Pulse, useHoverIntent } from "../motion";

function setReducedMotion(matches: boolean) {
  // motion/react's useReducedMotion reads matchMedia("(prefers-reduced-motion)").
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("CountUp", () => {
  it("AC2.4 — reduced motion renders the final value instantly", () => {
    setReducedMotion(true);
    render(<CountUp value={1234} format={(n) => `$${Math.round(n)}`} />);
    expect(screen.getByTestId("count-up").textContent).toBe("$1234");
  });

  it("AC2.1 — animates toward and settles on the new value", async () => {
    setReducedMotion(false);
    render(<CountUp value={1000} durationMs={50} format={(n) => String(Math.round(n))} />);
    // Let rAF frames flush; final settled value must equal the target.
    await new Promise((r) => setTimeout(r, 120));
    expect(screen.getByTestId("count-up").textContent).toBe("1000");
  });
});

describe("Pulse", () => {
  it("AC2.4 — reduced motion renders a plain wrapper (no animation)", () => {
    setReducedMotion(true);
    const { container } = render(
      <Pulse pulseKey="x">
        <span>node</span>
      </Pulse>,
    );
    expect(container.textContent).toBe("node");
  });
});

describe("useHoverIntent", () => {
  it("AC2.2 — fires only after the 250ms dwell, cancels on early leave", () => {
    vi.useFakeTimers();
    const onIntent = vi.fn();
    const { result } = renderHook(() => useHoverIntent(onIntent, 250));

    act(() => result.current.onMouseEnter());
    act(() => vi.advanceTimersByTime(200));
    expect(onIntent).not.toHaveBeenCalledWith(true); // not yet — under dwell

    act(() => vi.advanceTimersByTime(60));
    expect(onIntent).toHaveBeenCalledWith(true); // 260ms > 250ms

    onIntent.mockClear();
    act(() => result.current.onMouseEnter());
    act(() => result.current.onMouseLeave()); // leave before dwell
    act(() => vi.advanceTimersByTime(300));
    expect(onIntent).not.toHaveBeenCalledWith(true);
    expect(onIntent).toHaveBeenCalledWith(false);
  });
});
