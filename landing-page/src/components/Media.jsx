import { asset } from '../lib/content';
import { Rich } from './ui';

function Visual({ media, priority }) {
  const loading = priority ? 'eager' : 'lazy';
  const pixel = media.frame === 'lcd' || media.pixelated;

  if (media.type === 'video') {
    const autoplay = Boolean(media.autoplay);
    return (
      <video
        className="block h-auto w-full bg-black"
        poster={asset(media.poster)}
        controls={!autoplay}
        autoPlay={autoplay}
        muted={autoplay || media.muted}
        loop={autoplay}
        playsInline
        preload={autoplay || priority ? 'auto' : 'none'}
        width={media.width}
        height={media.height}
        aria-label={media.alt}
      >
        {media.webm ? <source src={asset(media.webm)} type="video/webm" /> : null}
        <source src={asset(media.src)} type="video/mp4" />
      </video>
    );
  }

  return (
    <img
      src={asset(media.src)}
      alt={media.alt ?? ''}
      loading={loading}
      decoding="async"
      width={media.width}
      height={media.height}
      className={`block h-auto w-full ${pixel ? 'pixelated' : ''}`}
    />
  );
}

function Frame({ media, children }) {
  if (media.frame === 'window') {
    return (
      <div className="overflow-hidden rounded-xl border border-line/60 bg-card shadow-card">
        <div className="flex h-9 items-center gap-2 border-b border-line/60 bg-soft px-4" aria-hidden="true">
          <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
          <span className="h-3 w-3 rounded-full bg-[#febc2e]" />
          <span className="h-3 w-3 rounded-full bg-[#28c840]" />
          {media.title ? <span className="ml-3 truncate font-mono text-xs text-muted">{media.title}</span> : null}
        </div>
        {children}
      </div>
    );
  }
  if (media.frame === 'lcd') {
    return (
      <div className="rounded-[22px] bg-[linear-gradient(145deg,#2b2f35,#16181c)] p-3 shadow-card ring-1 ring-white/10 sm:p-4">
        <div className="overflow-hidden rounded-lg ring-1 ring-black/60">{children}</div>
      </div>
    );
  }
  if (media.frame === 'plain') return <div className="overflow-hidden rounded-xl">{children}</div>;
  return <div className="overflow-hidden rounded-xl border border-line/60 bg-card shadow-card">{children}</div>;
}

export function Media({ media, priority = false, className = '' }) {
  if (!media?.src) return null;
  return (
    <figure className={className}>
      <Frame media={media}>
        <Visual media={media} priority={priority} />
      </Frame>
      {media.caption ? (
        <figcaption className="mt-3 text-sm leading-relaxed text-muted">
          <Rich text={media.caption} />
        </figcaption>
      ) : null}
    </figure>
  );
}
