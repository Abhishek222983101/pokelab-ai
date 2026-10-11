import { frontSprite, backSprite } from '@/lib/roster';
import { cx } from './ui';

/**
 * A Pokémon sprite (Showdown Gen 5, unpacked by assets/build_atlases.py). Pixelated, never smoothed.
 * Static frame on purpose: the animated GIF atlases live in the Phaser scenes, where the Director owns timing.
 */
export function Mon({
  species,
  size = 64,
  back,
  shadow,
  className,
  title,
}: {
  species: string;
  size?: number;
  back?: boolean;
  shadow?: boolean;
  className?: string;
  title?: string;
}) {
  return (
    <span className={cx('relative inline-flex flex-none items-end justify-center', className)} style={{ width: size, height: size }}>
      {shadow && <i aria-hidden="true" className="mon-shadow" style={{ width: size * 0.7 }} />}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={back ? backSprite(species) : frontSprite(species)}
        alt={title ?? ''}
        aria-hidden={title ? undefined : true}
        draggable={false}
        style={{ height: '100%', width: 'auto', maxWidth: '100%', objectFit: 'contain', imageRendering: 'pixelated', position: 'relative' }}
      />
    </span>
  );
}
