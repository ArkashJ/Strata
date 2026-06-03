// Strata-themed Clerk appearance for the night canvas. Uses only the documented
// `variables` theming primitive (accent, text, inputs, radius) — robust across
// Clerk versions — and lets our own `.glass` panel own the container. The
// SignIn/SignUp surfaces then read as indigo-on-navy, matching the landing.
export const strataClerkAppearance = {
  variables: {
    colorPrimary: "#7c7cf0",
    colorText: "#f6f7fc",
    colorTextSecondary: "#9aa3c2",
    colorInputText: "#f6f7fc",
    colorInputBackground: "rgba(255,255,255,0.05)",
    colorBackground: "transparent",
    colorNeutral: "#f6f7fc",
    borderRadius: "10px",
    fontFamily: "var(--font-ui)",
  },
};
