import { useSyncExternalStore } from "react";

const emptySubscribe = () => () => {};

/**
 * False on the server and on the first client (hydration) render, true after.
 *
 * Why: our list pages fetch with react-query in client components. There is no
 * data during SSR, so the server renders a skeleton — but React 19's concurrent
 * hydration can commit the loaded cards (the local API resolves in <50ms),
 * making the first client paint diverge from the server HTML. Gating the data
 * branch on this flag forces the first client render to also be the skeleton, so
 * server and client agree; the real data renders on the next commit.
 *
 * Implemented with useSyncExternalStore (not useEffect+setState) so it returns
 * the server snapshot during hydration with no set-state-in-effect cascade.
 */
export function useHasMounted(): boolean {
  return useSyncExternalStore(
    emptySubscribe,
    () => true,
    () => false,
  );
}
