// Minimal next/image stub — renders a plain <img> so components that import
// Image from "next/image" render without the Next.js image optimizer.
import type { ImgHTMLAttributes } from "react";

type ImageProps = ImgHTMLAttributes<HTMLImageElement> & {
  src: string;
  alt: string;
  fill?: boolean;
  priority?: boolean;
  quality?: number;
  sizes?: string;
  placeholder?: string;
  blurDataURL?: string;
};

export default function Image({
  fill: _fill,
  priority: _priority,
  quality: _quality,
  placeholder: _placeholder,
  blurDataURL: _blur,
  ...rest
}: ImageProps) {
  // biome-ignore lint/a11y/useAltText: alt is forwarded via ...rest (ImageProps requires alt: string)
  return <img {...rest} />;
}
