// Stub for next/font/google — font variables are already declared in globals.css
// via @theme inline, so we just return an empty className + variable.
type FontResult = { className: string; variable: string; style: { fontFamily: string } };

const makeFont =
  (varName: string) =>
  (_opts?: Record<string, unknown>): FontResult => ({
    className: "",
    variable: varName,
    style: { fontFamily: varName },
  });

export const Geist = makeFont("--font-ui");
export const Geist_Mono = makeFont("--font-mono");
export const Instrument_Serif = makeFont("--font-display");
export const Inter = makeFont("--font-ui");
