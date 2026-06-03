// Minimal next/navigation stub — exposes no-op hooks so components that import
// from next/navigation compile without the Next.js router runtime.
export const useRouter = () => ({
  push: () => {},
  replace: () => {},
  back: () => {},
  forward: () => {},
  prefetch: () => {},
  refresh: () => {},
});

export const usePathname = () => "/";
export const useSearchParams = () => new URLSearchParams();
export const useParams = () => ({});
export const notFound = () => {};
export const redirect = () => {};
